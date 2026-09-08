"""SQLAlchemy implementation of TranscriptRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    ApprovedSceneText as OrmApprovedSceneText,
    CatalogItem as OrmCatalogItem,
    ContentVersion as OrmContentVersion,
    LanguageAnalysisJob as OrmLanguageAnalysisJob,
    Scene as OrmScene,
    TranscriptRevision as OrmTranscriptRevision,
)
from jplearn_api.application.ports.repositories import ApprovedSceneSearchResult
from jplearn_api.domain.errors import RevisionConflictError
from jplearn_api.domain.search import (
    calculate_highlights_and_match_kind,
    decode_search_cursor,
    encode_search_cursor,
    search_candidate_terms,
)
from jplearn_api.domain.transcript import (
    ApprovedSceneText,
    LanguageAnalysisJob,
    LanguageAnalysisJobStatus,
    TranscriptProvenance,
    TranscriptRevision,
    TranscriptSegment,
    TranscriptStatus,
)


def _strip_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class SqlAlchemyTranscriptRepository:
    """SQLAlchemy adapter for TranscriptRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, orm: OrmTranscriptRevision) -> TranscriptRevision:
        segments = [
            TranscriptSegment(
                scene_id=s.get("scene_id", ""),
                text_ja=s.get("text_ja", ""),
            )
            for s in (orm.segments or [])
        ]
        return TranscriptRevision(
            id=orm.id,
            catalog_item_id=orm.catalog_item_id,
            content_version_id=orm.content_version_id,
            revision=orm.revision,
            status=TranscriptStatus(orm.status),
            segments=segments,
            provenance=TranscriptProvenance(orm.provenance),
            created_by=orm.created_by,
            approved_by=orm.approved_by,
            return_reason=orm.return_reason,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_latest_revision(
        self,
        catalog_item_id: str,
        content_version_id: str,
    ) -> TranscriptRevision | None:
        stmt = (
            select(OrmTranscriptRevision)
            .where(
                OrmTranscriptRevision.catalog_item_id == catalog_item_id,
                OrmTranscriptRevision.content_version_id == content_version_id,
            )
            .order_by(desc(OrmTranscriptRevision.revision))
            .limit(1)
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm)

    async def get_by_revision(
        self,
        catalog_item_id: str,
        content_version_id: str,
        revision: int,
    ) -> TranscriptRevision | None:
        stmt = select(OrmTranscriptRevision).where(
            OrmTranscriptRevision.catalog_item_id == catalog_item_id,
            OrmTranscriptRevision.content_version_id == content_version_id,
            OrmTranscriptRevision.revision == revision,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm)

    async def get_revision_by_id(
        self,
        revision_id: str,
    ) -> TranscriptRevision | None:
        stmt = select(OrmTranscriptRevision).where(OrmTranscriptRevision.id == revision_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm)

    async def save_revision(
        self,
        rev: TranscriptRevision,
        expected_revision: int | None = None,
    ) -> TranscriptRevision:
        stmt = select(OrmTranscriptRevision).where(OrmTranscriptRevision.id == rev.id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        seg_dicts = [{"scene_id": s.scene_id, "text_ja": s.text_ja} for s in rev.segments]

        if orm:
            exp_rev = expected_revision if expected_revision is not None else (rev.revision - 1 if rev.revision > orm.revision else orm.revision)
            from sqlalchemy import update
            stmt_update = (
                update(OrmTranscriptRevision)
                .where(
                    OrmTranscriptRevision.id == rev.id,
                    OrmTranscriptRevision.revision == exp_rev,
                )
                .values(
                    revision=rev.revision,
                    status=rev.status.value if hasattr(rev.status, "value") else str(rev.status),
                    segments=seg_dicts,
                    provenance=rev.provenance.value if hasattr(rev.provenance, "value") else str(rev.provenance),
                    approved_by=rev.approved_by,
                    return_reason=rev.return_reason,
                    updated_at=now,
                )
            )
            upd_res = await self._session.execute(stmt_update)
            if upd_res.rowcount == 0:
                raise RevisionConflictError(
                    f"Atomic CAS failed for transcript '{rev.id}': expected revision {exp_rev}"
                )
            # Re-read or refresh updated values
            stmt_reload = select(OrmTranscriptRevision).where(OrmTranscriptRevision.id == rev.id)
            reload_res = await self._session.execute(stmt_reload)
            orm = reload_res.scalar_one()
        else:
            orm = OrmTranscriptRevision(
                id=rev.id,
                catalog_item_id=rev.catalog_item_id,
                content_version_id=rev.content_version_id,
                revision=rev.revision,
                status=rev.status.value if hasattr(rev.status, "value") else str(rev.status),
                segments=seg_dicts,
                provenance=rev.provenance.value if hasattr(rev.provenance, "value") else str(rev.provenance),
                created_by=rev.created_by,
                approved_by=rev.approved_by,
                return_reason=rev.return_reason,
                created_at=now,
                updated_at=now,
            )
            self._session.add(orm)

        await self._session.flush()
        return self._to_domain(orm)

    async def activate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
        transcript_revision_id: str,
        texts: list[ApprovedSceneText],
    ) -> None:
        await self.deactivate_approved_scene_texts(catalog_item_id, content_version_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for t in texts:
            orm = OrmApprovedSceneText(
                id=t.id,
                catalog_item_id=t.catalog_item_id,
                content_version_id=t.content_version_id,
                scene_id=t.scene_id,
                transcript_revision_id=transcript_revision_id,
                text_ja=t.text_ja,
                scene_index=t.scene_index,
                start_time_seconds=t.start_time_seconds,
                end_time_seconds=t.end_time_seconds,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self._session.add(orm)
        await self._session.flush()

    async def deactivate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
    ) -> None:
        stmt = select(OrmApprovedSceneText).where(
            OrmApprovedSceneText.catalog_item_id == catalog_item_id,
            OrmApprovedSceneText.content_version_id == content_version_id,
            OrmApprovedSceneText.is_active.is_(True),
        )
        res = await self._session.execute(stmt)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for row in res.scalars().all():
            row.is_active = False
            row.updated_at = now
        await self._session.flush()

    async def create_language_analysis_job(
        self,
        job: LanguageAnalysisJob,
    ) -> LanguageAnalysisJob:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        orm = OrmLanguageAnalysisJob(
            id=job.id,
            catalog_item_id=job.catalog_item_id,
            transcript_revision_id=job.transcript_revision_id,
            idempotency_key=job.idempotency_key,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            results=job.results,
            error_message=job.error_message,
            created_by=job.created_by,
            created_at=now,
            completed_at=_strip_tz(job.completed_at),
        )
        self._session.add(orm)
        await self._session.flush()
        return job

    async def get_language_analysis_job(self, job_id: str) -> LanguageAnalysisJob | None:
        stmt = select(OrmLanguageAnalysisJob).where(OrmLanguageAnalysisJob.id == job_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return LanguageAnalysisJob(
            id=orm.id,
            catalog_item_id=orm.catalog_item_id,
            transcript_revision_id=orm.transcript_revision_id,
            idempotency_key=orm.idempotency_key,
            status=LanguageAnalysisJobStatus(orm.status),
            results=orm.results,
            error_message=orm.error_message,
            created_by=orm.created_by,
            created_at=orm.created_at,
            completed_at=orm.completed_at,
        )

    async def get_language_analysis_job_by_idempotency_key(
        self,
        catalog_item_id: str,
        idempotency_key: str,
    ) -> LanguageAnalysisJob | None:
        stmt = select(OrmLanguageAnalysisJob).where(
            OrmLanguageAnalysisJob.catalog_item_id == catalog_item_id,
            OrmLanguageAnalysisJob.idempotency_key == idempotency_key,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return LanguageAnalysisJob(
            id=orm.id,
            catalog_item_id=orm.catalog_item_id,
            transcript_revision_id=orm.transcript_revision_id,
            idempotency_key=orm.idempotency_key,
            status=LanguageAnalysisJobStatus(orm.status),
            results=orm.results,
            error_message=orm.error_message,
            created_by=orm.created_by,
            created_at=orm.created_at,
            completed_at=orm.completed_at,
        )

    async def search_approved_scenes(
        self,
        q: str,
        effective_max_ci: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[ApprovedSceneSearchResult], str | None, int]:
        # 1. Determine index generation
        gen_stmt = select(func.max(OrmApprovedSceneText.updated_at)).where(
            OrmApprovedSceneText.is_active.is_(True)
        )
        gen_res = await self._session.execute(gen_stmt)
        max_updated = gen_res.scalar_one_or_none()
        current_gen = str(int(max_updated.timestamp() * 1000)) if max_updated else "0"

        # 2. Decode cursor if provided
        offset = 0
        if cursor:
            cursor_gen, cursor_offset = decode_search_cursor(cursor)
            if cursor_gen != current_gen:
                raise RevisionConflictError("Index generation mismatch, search results refreshed")
            offset = cursor_offset

        # 3. Narrow candidates in PostgreSQL before applying deterministic
        # ranking/highlight rules in Python.
        terms = search_candidate_terms(q)
        text_column = OrmApprovedSceneText.text_ja
        term_filter = and_(*(text_column.contains(term, autoescape=True) for term in terms))
        candidate_filter = or_(
            text_column.contains(q, autoescape=True),
            term_filter,
        )
        stmt = (
            select(
                OrmApprovedSceneText.catalog_item_id,
                OrmApprovedSceneText.content_version_id,
                OrmApprovedSceneText.scene_id,
                OrmApprovedSceneText.scene_index,
                OrmApprovedSceneText.start_time_seconds,
                OrmApprovedSceneText.end_time_seconds,
                OrmApprovedSceneText.text_ja,
                OrmCatalogItem.ci_level,
                OrmCatalogItem.topic_id,
                OrmScene.title_jp,
            )
            .join(OrmCatalogItem, OrmCatalogItem.id == OrmApprovedSceneText.catalog_item_id)
            .join(OrmContentVersion, OrmContentVersion.id == OrmApprovedSceneText.content_version_id)
            .join(OrmScene, OrmScene.id == OrmApprovedSceneText.scene_id)
            .where(
                OrmApprovedSceneText.is_active.is_(True),
                OrmCatalogItem.status == "published",
                OrmContentVersion.is_published.is_(True),
                OrmCatalogItem.ci_level <= effective_max_ci,
                candidate_filter,
            )
            .order_by(
                OrmApprovedSceneText.catalog_item_id,
                OrmApprovedSceneText.scene_index,
            )
        )
        res = await self._session.execute(stmt)
        rows = res.all()

        # 4. Deterministic relevance matching & highlighting for the narrowed set
        exact_matches: list[ApprovedSceneSearchResult] = []
        token_matches: list[ApprovedSceneSearchResult] = []

        for row in rows:
            text_ja = row.text_ja
            match_kind, spans = calculate_highlights_and_match_kind(text_ja, q)
            if match_kind is None:
                continue

            item = ApprovedSceneSearchResult(
                catalog_item_id=row.catalog_item_id,
                content_version_id=row.content_version_id,
                scene_id=row.scene_id,
                scene_index=row.scene_index,
                start_time_seconds=row.start_time_seconds,
                end_time_seconds=row.end_time_seconds,
                matched_text_ja=text_ja,
                highlight_spans=spans,
                match_kind=match_kind,
                ci_level=row.ci_level,
                topic_id=row.topic_id,
                title_jp=row.title_jp,
            )
            if match_kind == "exact_phrase":
                exact_matches.append(item)
            else:
                token_matches.append(item)

        # Combine: exact_phrase first, token_match second
        all_matches = exact_matches + token_matches
        total_estimated = len(all_matches)

        # Slice by offset and limit
        page = all_matches[offset : offset + limit]
        next_cursor = None
        if offset + limit < total_estimated:
            next_cursor = encode_search_cursor(current_gen, offset + limit)

        return page, next_cursor, total_estimated
