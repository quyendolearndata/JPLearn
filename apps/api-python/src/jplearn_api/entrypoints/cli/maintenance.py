"""Maintenance CLI for background worker tasks (e.g. History Deletions purge worker).

Usage:
    jplearn-maintenance purge-history [--once] [--limit N]
    jplearn-maintenance sweep-ai-attempts [--limit N]
    jplearn-maintenance inventory-media-integrity [--limit N]
    python -m jplearn_api.entrypoints.cli.maintenance purge-history [--once]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy import text

from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
from jplearn_api.application.handlers.activity import handle_execute_history_deletion_worker
from jplearn_api.application.handlers.ai_attempts import sweep_expired_ai_attempts
from jplearn_api.bootstrap import create_uow
from jplearn_api.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("jplearn_maintenance")


async def run_history_purges(once: bool = False, max_jobs: int | None = None) -> int:
    """Execute queued history deletions."""
    settings = get_settings()
    engine, session_maker = create_engine_and_sessions(settings)

    processed = 0
    try:
        while True:
            async with session_maker() as session:
                uow = create_uow(session)
                job = await handle_execute_history_deletion_worker(uow)
                if job:
                    await session.commit()
                    processed += 1
                    status_val = job.status.value if hasattr(job.status, "value") else str(job.status)
                    logger.info(
                        "Processed history deletion job %s for user %s: status=%s, deleted=%d",
                        job.id,
                        job.user_id,
                        status_val,
                        job.records_deleted,
                    )
                else:
                    if once:
                        break
                    await asyncio.sleep(2)

            if max_jobs is not None and processed >= max_jobs:
                break
            if once and job is None:
                break
    finally:
        await engine.dispose()

    return processed


async def run_ai_attempt_sweep(limit: int = 100) -> int:
    """Quarantine expired provider attempts without retrying or releasing quota."""
    settings = get_settings()
    engine, session_maker = create_engine_and_sessions(settings)
    try:
        async with session_maker() as session:
            return await sweep_expired_ai_attempts(create_uow(session), limit=limit)
    finally:
        await engine.dispose()


async def inventory_media_integrity(limit: int = 100) -> dict:
    """Return a read-only inventory of legacy media that must repeat QA."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    settings = get_settings()
    engine, _ = create_engine_and_sessions(settings)
    try:
        async with engine.connect() as conn:
            media_total = await conn.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM media_assets
                    WHERE measured_duration_ms IS NULL
                       OR source_sha256 IS NULL
                       OR (hls_url IS NOT NULL AND hls_bundle_sha256 IS NULL)
                    """
                )
            )
            media_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT a.id, a.catalog_item_id, c.status AS catalog_status,
                               a.storage_key, a.hls_url,
                               a.measured_duration_ms IS NULL AS missing_measured_duration,
                               a.source_sha256 IS NULL AS missing_source_sha256,
                               a.hls_url IS NOT NULL AND a.hls_bundle_sha256 IS NULL
                                   AS missing_hls_bundle_sha256
                        FROM media_assets a
                        JOIN catalog_items c ON c.id = a.catalog_item_id
                        WHERE a.measured_duration_ms IS NULL
                           OR a.source_sha256 IS NULL
                           OR (a.hls_url IS NOT NULL AND a.hls_bundle_sha256 IS NULL)
                        ORDER BY a.catalog_item_id, a.id
                        LIMIT :limit
                        """
                    ),
                    {"limit": limit},
                )
            ).mappings().all()

            version_total = await conn.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM content_versions
                    WHERE (is_frozen OR is_published)
                      AND (
                          media_asset_id IS NULL
                          OR media_storage_key IS NULL
                          OR measured_duration_ms IS NULL
                          OR source_sha256 IS NULL
                          OR duration_source = 'legacy_metadata'
                          OR (media_hls_url IS NOT NULL AND hls_bundle_sha256 IS NULL)
                      )
                    """
                )
            )
            version_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT v.id, v.catalog_item_id, v.version_number,
                               v.is_frozen, v.is_published,
                               v.media_asset_id IS NULL AS missing_media_asset_id,
                               v.media_storage_key IS NULL AS missing_media_storage_key,
                               v.measured_duration_ms IS NULL AS missing_measured_duration,
                               v.source_sha256 IS NULL AS missing_source_sha256,
                               v.duration_source = 'legacy_metadata' AS legacy_duration,
                               v.media_hls_url IS NOT NULL AND v.hls_bundle_sha256 IS NULL
                                   AS missing_hls_bundle_sha256
                        FROM content_versions v
                        WHERE (v.is_frozen OR v.is_published)
                          AND (
                              v.media_asset_id IS NULL
                              OR v.media_storage_key IS NULL
                              OR v.measured_duration_ms IS NULL
                              OR v.source_sha256 IS NULL
                              OR v.duration_source = 'legacy_metadata'
                              OR (v.media_hls_url IS NOT NULL AND v.hls_bundle_sha256 IS NULL)
                          )
                        ORDER BY v.catalog_item_id, v.version_number, v.id
                        LIMIT :limit
                        """
                    ),
                    {"limit": limit},
                )
            ).mappings().all()
    finally:
        await engine.dispose()

    def serialize(rows) -> list[dict]:
        return [dict(row) for row in rows]

    return {
        "media_assets": {"candidate_count": int(media_total or 0), "candidates": serialize(media_rows)},
        "pinned_versions": {
            "candidate_count": int(version_total or 0),
            "candidates": serialize(version_rows),
        },
        "truncated": bool((media_total or 0) > limit or (version_total or 0) > limit),
        "required_action": "re-upload or re-register the source, then repeat level QA before publish",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="JPLearn background maintenance worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    purge_parser = subparsers.add_parser("purge-history", help="Run pending watch history purges")
    purge_parser.add_argument("--once", action="store_true", help="Process all currently queued jobs and exit")
    purge_parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to process")

    sweep_parser = subparsers.add_parser(
        "sweep-ai-attempts",
        help="Quarantine expired AI attempts for operator reconciliation",
    )
    sweep_parser.add_argument("--limit", type=int, default=100, help="Maximum attempts per sweep (1-1000)")

    inventory_parser = subparsers.add_parser(
        "inventory-media-integrity",
        help="List legacy media and pinned versions that require integrity re-QA",
    )
    inventory_parser.add_argument("--limit", type=int, default=100, help="Maximum rows per section (1-1000)")

    args = parser.parse_args()

    if args.command == "purge-history":
        count = asyncio.run(run_history_purges(once=args.once, max_jobs=args.limit))
        logger.info("Purge maintenance completed. Processed %d jobs.", count)
        sys.exit(0)
    if args.command == "sweep-ai-attempts":
        count = asyncio.run(run_ai_attempt_sweep(limit=args.limit))
        logger.info("AI attempt sweep completed. Quarantined %d attempts.", count)
        sys.exit(0)
    if args.command == "inventory-media-integrity":
        if not 1 <= args.limit <= 1000:
            parser.error("--limit must be between 1 and 1000")
        report = asyncio.run(inventory_media_integrity(limit=args.limit))
        print(json.dumps(report, indent=2, sort_keys=True))
        sys.exit(0)


if __name__ == "__main__":
    main()
