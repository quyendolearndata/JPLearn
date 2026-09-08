"""AI Worker CLI for durable content jobs queue (ADR-007 PR8).

Usage:
    jplearn-ai-worker [--once] [--max-jobs N]
    python -m jplearn_api.entrypoints.cli.ai_worker [--once]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from uuid import uuid4

from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
from jplearn_api.application.handlers.content_jobs import handle_execute_ai_worker_step
from jplearn_api.application.ports.ai_provider import (
    AiTranscriptionPort,
    AiTranscriptionResult,
    AiUsageRecord,
)
from jplearn_api.bootstrap import create_uow
from jplearn_api.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("jplearn_ai_worker")


class DefaultTrialTranscriber(AiTranscriptionPort):
    """Default trial transcription adapter for developer testing and local evaluation."""

    def __init__(self, allow_synthetic: bool | None = None) -> None:
        if allow_synthetic is not None:
            self.allow_synthetic = allow_synthetic
        else:
            settings = get_settings()
            self.allow_synthetic = (
                settings.environment in ("local", "test")
                and settings.enable_trial_transcriber
            )

    async def transcribe_and_segment(
        self,
        media_storage_key: str,
        media_duration_seconds: int,
        language: str = "ja",
    ) -> AiTranscriptionResult:
        if not self.allow_synthetic:
            raise RuntimeError(
                "External AI transcription provider not configured. "
                "Synthetic trial mode is only permitted when environment is local/test and enable_trial_transcriber=True."
            )
        logger.info(
            "Transcribing media %s (%ds, lang=%s)",
            media_storage_key,
            media_duration_seconds,
            language,
        )
        # Synthetic evaluation segments for trial run
        segments = [
            {
                "scene_id": "scene-1",
                "text_ja": "こんにちは、世界！",
                "start_ms": 0,
                "end_ms": min(2000, media_duration_seconds * 1000),
            }
        ]
        usage = AiUsageRecord(
            audio_seconds=media_duration_seconds,
            input_tokens=500,
            output_tokens=150,
            cost_micros=100000,
            provider_request_id=f"trial-{uuid4().hex}",
            currency="USD",
            policy_version="v1",
        )
        return AiTranscriptionResult(
            segments=segments,
            usage=usage,
            provenance={"provider": "trial_transcriber", "model": "local-v1"},
        )


async def run_ai_worker(
    once: bool = False,
    max_jobs: int | None = None,
    poll_interval: float = 2.0,
    ai_provider: AiTranscriptionPort | None = None,
) -> int:
    """Run the AI worker claiming and executing queued content jobs."""
    settings = get_settings()
    if not settings.staff_ai_enabled:
        logger.info("AI worker disabled; no jobs claimed")
        return 0
    if ai_provider is None:
        if not (settings.environment in ("local", "test") and settings.enable_trial_transcriber):
            raise RuntimeError(
                "AI provider unavailable: configure a real adapter before running this worker. "
                "Synthetic mode requires explicit opt-in in local/test. No jobs were claimed."
            )
        provider = DefaultTrialTranscriber(allow_synthetic=True)
    else:
        if isinstance(ai_provider, DefaultTrialTranscriber) and settings.environment not in ("local", "test"):
            raise RuntimeError("Synthetic transcription is forbidden outside local/test")
        provider = ai_provider
    engine, session_maker = create_engine_and_sessions(settings)

    processed = 0
    try:
        while True:
            if not settings.staff_ai_enabled:
                break
            async with session_maker() as session:
                uow = create_uow(session)
                job = await handle_execute_ai_worker_step(
                    uow, provider, capability_enabled=settings.staff_ai_enabled,
                )
                if job:
                    await session.commit()
                    processed += 1
                    logger.info(
                        "Processed content job %s: task=%s, status=%s",
                        job.id,
                        job.task,
                        job.status,
                    )
                else:
                    if once:
                        break
                    await asyncio.sleep(poll_interval)

            if max_jobs is not None and processed >= max_jobs:
                break
            if once and job is None:
                break
    finally:
        await engine.dispose()

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="JPLearn AI Content Jobs Worker")
    parser.add_argument("--once", action="store_true", help="Process queued jobs once and exit")
    parser.add_argument("--max-jobs", type=int, default=None, help="Maximum number of jobs to process")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    try:
        count = asyncio.run(
            run_ai_worker(
                once=args.once,
                max_jobs=args.max_jobs,
                poll_interval=args.poll_interval,
            )
        )
        logger.info("AI Worker terminated cleanly. Jobs processed: %d", count)
    except KeyboardInterrupt:
        logger.info("AI Worker interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
