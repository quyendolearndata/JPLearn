"""Application handlers for Japanese Transcript and Language Analysis (ADR-007 PR8a).

Enforces:
- FR-JPA-001 / UC-T10: Japanese transcript workflow (draft -> qa_submitted -> approved / returned_to_draft).
- Optimistic concurrency control (CAS expected_revision).
- Content version alignment: every segment must map to a valid scene in the version.
- Validation limits (<= 100 segments/clip, <= 500 chars/segment, <= 20,000 total chars).
- Search projection generation upon approve, and revocation upon return_to_draft.
- Pure Python Unicode tokenization and code point offset analysis.
- Zero banned textbook/grammar pedagogy exposure (FR-NEG).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from jplearn_api.application.commands import (
    ApproveTranscriptCommand,
    CreateLanguageAnalysisJobCommand,
    ReturnTranscriptToDraftCommand,
    SaveTranscriptDraftCommand,
    SubmitTranscriptQACommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetLanguageAnalysisJobQuery,
    GetTranscriptQuery,
)
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
    RevisionConflictError,
    ValidationError,
)
from jplearn_api.domain.transcript import (
    ApprovedSceneText,
    LanguageAnalysisJob,
    LanguageAnalysisJobStatus,
    TranscriptProvenance,
    TranscriptRevision,
    TranscriptSegment,
    TranscriptStatus,
    analyze_japanese_text,
)


async def handle_get_transcript(
    query: GetTranscriptQuery,
    uow: AsyncUnitOfWork,
) -> TranscriptRevision:
    """Retrieve the latest transcript revision for a catalog item content version."""
    async with uow:
        item = await uow.catalog.get_by_id(query.catalog_item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")

        content_version_id = query.content_version_id
        if not content_version_id:
            published_v = await uow.content.get_published_by_catalog_item_id(query.catalog_item_id)
            if published_v:
                content_version_id = published_v.id
            else:
                draft_v = await uow.content.get_current_draft_by_catalog_item_id(query.catalog_item_id)
                if draft_v:
                    content_version_id = draft_v.id
                else:
                    raise EntityNotFoundError("Catalog item has no content version")

        rev = await uow.transcripts.get_latest_revision(query.catalog_item_id, content_version_id)
        if rev is None:
            raise EntityNotFoundError("Transcript not found for this content version")
        return rev


async def handle_save_transcript_draft(
    cmd: SaveTranscriptDraftCommand,
    uow: AsyncUnitOfWork,
    *,
    auto_commit: bool = True,
) -> TranscriptRevision:
    """Create or update a draft transcript revision with CAS concurrency."""
    async with uow:
        item = await uow.catalog.get_by_id(cmd.catalog_item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")

        version = await uow.content.get_by_id(cmd.content_version_id)
        if version is None or version.catalog_item_id != cmd.catalog_item_id:
            raise EntityNotFoundError(f"Content version '{cmd.content_version_id}' not found for catalog item")

        # Validate that all segments reference valid scenes in this content version
        valid_scene_ids = {s.id for s in version.scenes}
        segments: list[TranscriptSegment] = []
        for s in cmd.segments:
            scene_id = s.get("scene_id", "").strip()
            text_ja = s.get("text_ja", "")
            if scene_id not in valid_scene_ids:
                raise ValidationError(
                    f"Scene '{scene_id}' does not belong to content version '{cmd.content_version_id}'"
                )
            segments.append(TranscriptSegment(scene_id=scene_id, text_ja=text_ja))

        provenance = (
            TranscriptProvenance(cmd.provenance)
            if hasattr(TranscriptProvenance, cmd.provenance.upper())
            else TranscriptProvenance.MANUAL_TEACHER
        )

        existing = await uow.transcripts.get_latest_revision(cmd.catalog_item_id, cmd.content_version_id)
        now = datetime.now(timezone.utc)

        if existing is None:
            if cmd.expected_revision not in (0, 1):
                raise RevisionConflictError(
                    f"Expected revision {cmd.expected_revision}, but transcript does not exist yet (expected 0 or 1)"
                )
            rev = TranscriptRevision(
                id=f"tr_{uuid4().hex[:16]}",
                catalog_item_id=cmd.catalog_item_id,
                content_version_id=cmd.content_version_id,
                revision=1,
                status=TranscriptStatus.DRAFT,
                segments=segments,
                provenance=provenance,
                created_by=cmd.user_id,
                created_at=now,
                updated_at=now,
            )
            rev.validate_bounds()
            saved = await uow.transcripts.save_revision(rev)
            if auto_commit:
                await uow.commit()
            return saved

        # Existing revision found: check CAS
        if existing.revision != cmd.expected_revision:
            raise RevisionConflictError(
                f"Expected revision {cmd.expected_revision}, but current revision is {existing.revision}"
            )

        if existing.status == TranscriptStatus.QA_SUBMITTED:
            raise InvalidDomainStateError(
                "Cannot edit transcript while it is submitted for QA. Return to draft or approve first."
            )

        if existing.status == TranscriptStatus.APPROVED:
            # Editing an approved transcript forks into a new draft revision
            rev = TranscriptRevision(
                id=f"tr_{uuid4().hex[:16]}",
                catalog_item_id=cmd.catalog_item_id,
                content_version_id=cmd.content_version_id,
                revision=existing.revision + 1,
                status=TranscriptStatus.DRAFT,
                segments=segments,
                provenance=provenance,
                created_by=cmd.user_id,
                created_at=now,
                updated_at=now,
            )
            rev.validate_bounds()
            saved = await uow.transcripts.save_revision(rev)
            if auto_commit:
                await uow.commit()
            return saved

        # Existing revision is DRAFT or RETURNED_TO_DRAFT: update and bump revision
        existing.segments = segments
        existing.provenance = provenance
        existing.status = TranscriptStatus.DRAFT
        existing.return_reason = None
        existing.revision += 1
        existing.updated_at = now
        existing.validate_bounds()

        saved = await uow.transcripts.save_revision(existing, expected_revision=cmd.expected_revision)
        if auto_commit:
            await uow.commit()
        return saved


async def handle_submit_transcript_qa(
    cmd: SubmitTranscriptQACommand,
    uow: AsyncUnitOfWork,
) -> TranscriptRevision:
    """Submit a draft transcript revision for QA review."""
    async with uow:
        existing = await uow.transcripts.get_latest_revision(cmd.catalog_item_id, cmd.content_version_id)
        if existing is None:
            raise EntityNotFoundError("Transcript not found")
        if existing.revision != cmd.expected_revision:
            raise RevisionConflictError(
                f"Expected revision {cmd.expected_revision}, but current revision is {existing.revision}"
            )

        existing.submit_qa()
        existing.updated_at = datetime.now(timezone.utc)
        saved = await uow.transcripts.save_revision(existing, expected_revision=cmd.expected_revision)
        await uow.commit()
        return saved


async def handle_approve_transcript(
    cmd: ApproveTranscriptCommand,
    uow: AsyncUnitOfWork,
) -> TranscriptRevision:
    """Approve a transcript revision and activate search projection."""
    async with uow:
        existing = await uow.transcripts.get_latest_revision(cmd.catalog_item_id, cmd.content_version_id)
        if existing is None:
            raise EntityNotFoundError("Transcript not found")
        if existing.revision != cmd.expected_revision:
            raise RevisionConflictError(
                f"Expected revision {cmd.expected_revision}, but current revision is {existing.revision}"
            )

        existing.approve(cmd.user_id)
        existing.updated_at = datetime.now(timezone.utc)
        saved = await uow.transcripts.save_revision(existing, expected_revision=cmd.expected_revision)

        # Generate and activate search projection texts
        version = await uow.content.get_by_id(cmd.content_version_id)
        scene_map = {s.id: s for s in (version.scenes if version else [])}

        approved_texts: list[ApprovedSceneText] = []
        now = datetime.now(timezone.utc)
        for seg in existing.segments:
            sc = scene_map.get(seg.scene_id)
            if sc:
                approved_texts.append(
                    ApprovedSceneText(
                        id=f"ast_{uuid4().hex[:16]}",
                        catalog_item_id=cmd.catalog_item_id,
                        content_version_id=cmd.content_version_id,
                        scene_id=seg.scene_id,
                        transcript_revision_id=existing.id,
                        text_ja=seg.text_ja,
                        scene_index=sc.scene_index,
                        start_time_seconds=sc.start_time_seconds,
                        end_time_seconds=sc.end_time_seconds,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )

        await uow.transcripts.activate_approved_scene_texts(
            catalog_item_id=cmd.catalog_item_id,
            content_version_id=cmd.content_version_id,
            transcript_revision_id=existing.id,
            texts=approved_texts,
        )
        await uow.commit()
        return saved


async def handle_return_transcript_to_draft(
    cmd: ReturnTranscriptToDraftCommand,
    uow: AsyncUnitOfWork,
) -> TranscriptRevision:
    """Return a transcript revision to draft with a reason and deactivate search projection."""
    async with uow:
        existing = await uow.transcripts.get_latest_revision(cmd.catalog_item_id, cmd.content_version_id)
        if existing is None:
            raise EntityNotFoundError("Transcript not found")
        if existing.revision != cmd.expected_revision:
            raise RevisionConflictError(
                f"Expected revision {cmd.expected_revision}, but current revision is {existing.revision}"
            )

        existing.return_to_draft(cmd.reason)
        existing.updated_at = datetime.now(timezone.utc)
        saved = await uow.transcripts.save_revision(existing, expected_revision=cmd.expected_revision)

        # Deactivate approved search texts
        await uow.transcripts.deactivate_approved_scene_texts(
            catalog_item_id=cmd.catalog_item_id,
            content_version_id=cmd.content_version_id,
        )
        await uow.commit()
        return saved


async def handle_create_language_analysis_job(
    cmd: CreateLanguageAnalysisJobCommand,
    uow: AsyncUnitOfWork,
) -> LanguageAnalysisJob:
    """Execute tokenization and reading analysis for a transcript revision."""
    async with uow:
        if cmd.idempotency_key:
            existing_job = await uow.transcripts.get_language_analysis_job_by_idempotency_key(
                cmd.catalog_item_id, cmd.idempotency_key
            )
            if existing_job is not None:
                return existing_job

        # Find transcript revision
        rev: TranscriptRevision | None = None
        if cmd.transcript_revision_id:
            rev = await uow.transcripts.get_revision_by_id(cmd.transcript_revision_id)

        if rev is None:
            item = await uow.catalog.get_by_id(cmd.catalog_item_id)
            if item is None:
                raise EntityNotFoundError("Catalog item not found")

            pub_v = await uow.content.get_published_by_catalog_item_id(cmd.catalog_item_id)
            draft_v = await uow.content.get_current_draft_by_catalog_item_id(cmd.catalog_item_id)
            v_id = (pub_v.id if pub_v else None) or (draft_v.id if draft_v else None)
            if not v_id:
                raise EntityNotFoundError("No content version found for catalog item")

            rev = await uow.transcripts.get_latest_revision(cmd.catalog_item_id, v_id)
            if rev is None:
                raise EntityNotFoundError("Transcript revision not found")

        # Perform Japanese linguistic analysis
        analysis_segments: list[dict] = []
        for s in rev.segments:
            tokens = analyze_japanese_text(s.text_ja)
            analysis_segments.append(
                {
                    "scene_id": s.scene_id,
                    "text_ja": s.text_ja,
                    "tokens": [asdict(t) for t in tokens],
                }
            )

        now = datetime.now(timezone.utc)
        total_tokens = sum(len(s["tokens"]) for s in analysis_segments)
        job = LanguageAnalysisJob(
            id=f"laj_{uuid4().hex[:16]}",
            catalog_item_id=cmd.catalog_item_id,
            transcript_revision_id=rev.id,
            idempotency_key=cmd.idempotency_key,
            status=LanguageAnalysisJobStatus.COMPLETED,
            results={
                "strategy": "v1_rule_based_analyzer",
                "total_segments": len(analysis_segments),
                "total_tokens": total_tokens,
                "segments": analysis_segments,
            },
            error_message=None,
            created_by=cmd.user_id,
            created_at=now,
            completed_at=now,
        )

        saved = await uow.transcripts.create_language_analysis_job(job)
        await uow.commit()
        return saved


async def handle_get_language_analysis_job(
    query: GetLanguageAnalysisJobQuery,
    uow: AsyncUnitOfWork,
) -> LanguageAnalysisJob:
    """Retrieve details and token spans of a language analysis job."""
    async with uow:
        job = await uow.transcripts.get_language_analysis_job(query.job_id)
        if job is None:
            raise EntityNotFoundError("Language analysis job not found")
        return job
