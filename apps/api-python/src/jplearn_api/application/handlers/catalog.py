"""Catalog use case handlers (Pure Python)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from jplearn_api.application.commands import (
    ArchiveCatalogItemCommand,
    CreateCatalogItemCommand,
    PublishCatalogItemCommand,
    SubmitCatalogForQaCommand,
    UnpublishCatalogItemCommand,
    UpdateDraftCatalogItemCommand,
)
from jplearn_api.application.ports.repositories import CatalogQueryPort, CatalogRepository
from jplearn_api.application.media_integrity import inspect_hls_bundle
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetStaffCatalogItemQuery,
    ListPublishedCatalogQuery,
    ListStaffCatalogQuery,
)
from jplearn_api.application.read_models import CatalogItemPublicDTO, CatalogItemStaffDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.content import ContentVersion
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
    MediaInvariantError,
)


def _to_staff_dto(item: CatalogItem) -> CatalogItemStaffDTO:
    return CatalogItemStaffDTO(
        id=item.id,
        topic_id=item.topic_id,
        ci_level=item.ci_level,
        duration_seconds=item.duration_seconds,
        media_type=item.media_type,
        visual_support=item.visual_support,
        title_internal=item.title_internal,
        has_l1_translation=item.has_l1_translation,
        status=item.status,
        revision=item.revision,
        qa_round=item.qa_round,
    )



async def handle_create_catalog_item(
    cmd: CreateCatalogItemCommand,
    uow: AsyncUnitOfWork,
    *,
    id_generator: Callable[[], str] = lambda: str(uuid4()),
) -> CatalogItemStaffDTO:
    """Create new catalog item in draft status."""
    async with uow:
        topic_exists = await uow.catalog.topic_exists(cmd.topic_id)
        if not topic_exists:
            raise InvalidDomainStateError("Unknown topic_id")

        item = CatalogItem(
            id=id_generator(),
            topic_id=cmd.topic_id,
            ci_level=cmd.ci_level,
            duration_seconds=cmd.duration_seconds,
            media_type=cmd.media_type,
            visual_support=cmd.visual_support,
            title_internal=cmd.title_internal,
            created_by=cmd.created_by,
            has_l1_translation=False,
            spoken_language="ja",
            status="draft",
            media=[],
        )

        await uow.catalog.add(item)
        await uow.commit()

    return _to_staff_dto(item)


from jplearn_api.application.ports.repositories import (
    CatalogQueryPort,
    CatalogRepository,
    UpdateDraftResultStatus,
)


async def handle_submit_qa(
    cmd: SubmitCatalogForQaCommand,
    uow: AsyncUnitOfWork,
) -> CatalogItemStaffDTO:
    """Submit a draft item for QA."""
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.submit_for_qa()
        await uow.catalog.update(item)
        draft_version = await uow.content.get_current_draft_by_catalog_item_id(cmd.item_id)
        if draft_version is None and item.media:
            draft_version = ContentVersion(
                id=str(uuid4()), catalog_item_id=item.id,
                version_number=await uow.content.get_max_version_number(item.id) + 1,
            )
            await uow.content.save_draft(draft_version)
        if draft_version is not None:
            if not item.media:
                raise MediaInvariantError("Cannot submit scene content without media")
            asset = sorted(item.media, key=lambda media: media.id)[0]
            if draft_version.scenes and (asset.measured_duration_ms is None or not asset.source_sha256):
                raise MediaInvariantError("Legacy media must be reuploaded and measured before scene QA")
            if asset.measured_duration_ms is not None and any(
                scene.end_time_seconds * 1000 > asset.measured_duration_ms for scene in draft_version.scenes
            ):
                raise InvalidDomainStateError("Scene end exceeds measured media duration")
            draft_version.pin_source(
                asset.id,
                asset.storage_key,
                asset.hls_url,
                item.duration_seconds,
                asset.hls_bundle_sha256,
            )
            draft_version.measured_duration_ms = asset.measured_duration_ms
            draft_version.source_sha256 = asset.source_sha256
            if asset.measured_duration_ms is not None:
                draft_version.duration_source = "ffprobe"
            if draft_version.scenes and item.duration_seconds:
                for sc in draft_version.scenes:
                    if sc.end_time_seconds > item.duration_seconds:
                        raise InvalidDomainStateError(
                            f"Scene end time ({sc.end_time_seconds}s) exceeds clip duration ({item.duration_seconds}s)"
                        )
            draft_version.freeze_for_qa()
            await uow.content.update(draft_version)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_publish(
    cmd: PublishCatalogItemCommand,
    uow: AsyncUnitOfWork,
    storage: StoragePort,
) -> CatalogItemStaffDTO:
    """Inspect outside transactions, then revalidate the pinned identity under catalog lock."""
    async with uow:
        candidate = await uow.content.get_current_draft_by_catalog_item_id(cmd.item_id)
        probe_key = candidate.media_storage_key if candidate else None
        expected_checksum = candidate.source_sha256 if candidate else None
        expected_hls_checksum = candidate.hls_bundle_sha256 if candidate else None
        hls_asset_id = candidate.media_asset_id if candidate else None
    inspection = None
    if probe_key and expected_checksum:
        try:
            inspection = await storage.inspect_media(probe_key)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            raise MediaInvariantError("QA source cannot be verified") from exc
    hls_inspection = None
    if hls_asset_id and expected_hls_checksum:
        try:
            hls_inspection = await inspect_hls_bundle(storage, hls_asset_id)
        except (InvalidDomainStateError, ValueError, KeyError, FileNotFoundError) as exc:
            raise MediaInvariantError("QA HLS bundle cannot be verified") from exc
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")

        if item.status != "level_qa":
            raise InvalidDomainStateError("Only level_qa items can be published")

        if not item.media:
            raise MediaInvariantError("Cannot publish without media: upload a playback source first (FR-CAT-002)")

        for asset in item.media:
            exists = await storage.exists(asset.storage_key)
            if not exists:
                raise MediaInvariantError(
                    f"Cannot publish: media file missing from storage for asset {asset.id} (FR-CAT-002)",
                )

        if not any(r.qa_round == item.qa_round and r.decision == "approve" for r in item.reviews):
            raise InvalidDomainStateError("Current QA round must be approved before publishing")
        item.publish()
        await uow.catalog.update(item)
        draft_version = await uow.content.get_current_draft_by_catalog_item_id(cmd.item_id)
        if draft_version is not None:
            asset = next((a for a in item.media if a.id == draft_version.media_asset_id), None)
            if asset is None:
                raise ConflictError("QA source is missing; return to draft and submit again")
            draft_version.assert_source(
                asset.id,
                asset.storage_key,
                asset.hls_url,
                item.duration_seconds,
                asset.hls_bundle_sha256,
            )
            if draft_version.source_sha256 and (
                inspection is None or draft_version.media_storage_key != probe_key
                or inspection.sha256 != draft_version.source_sha256
                or inspection.duration_ms != draft_version.measured_duration_ms
            ):
                raise ConflictError("Media bytes changed since QA; upload a new source and repeat QA")
            if draft_version.hls_bundle_sha256 and (
                hls_inspection is None
                or hls_inspection.sha256 != draft_version.hls_bundle_sha256
            ):
                raise ConflictError("HLS bundle changed since QA; transcode and repeat QA")
            if draft_version.scenes and draft_version.duration_source != "ffprobe":
                raise MediaInvariantError("Legacy segmentation needs measured source and fresh QA")
            if draft_version.scenes and item.duration_seconds:
                for sc in draft_version.scenes:
                    if sc.end_time_seconds > item.duration_seconds:
                        raise InvalidDomainStateError(
                            f"Scene end time ({sc.end_time_seconds}s) exceeds clip duration ({item.duration_seconds}s)"
                        )
            from datetime import datetime, timezone
            draft_version.publish(datetime.now(timezone.utc))
            await uow.content.update(draft_version)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_unpublish(
    cmd: UnpublishCatalogItemCommand,
    uow: AsyncUnitOfWork,
) -> CatalogItemStaffDTO:
    """Unpublish a published item back to draft."""
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.unpublish()
        await uow.catalog.update(item)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_archive(
    cmd: ArchiveCatalogItemCommand,
    uow: AsyncUnitOfWork,
) -> None:
    """Archive a catalog item."""
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.archive()
        await uow.catalog.update(item)
        await uow.commit()


async def handle_list_published(
    query: ListPublishedCatalogQuery,
    query_port: CatalogQueryPort,
) -> list[CatalogItemPublicDTO]:
    """Retrieve published items formatted for public consumption."""
    return await query_port.list_published(query.ci_level)


async def handle_list_staff_catalog(
    query: ListStaffCatalogQuery,
    repo: CatalogRepository,
) -> list[CatalogItemStaffDTO]:
    """Retrieve internal catalog items with optional filtering and pagination."""
    items = await repo.list_staff(
        status=query.status,
        ci_level=query.ci_level,
        limit=query.limit,
        offset=query.offset,
    )
    return [_to_staff_dto(i) for i in items]


async def handle_get_staff_catalog_item(
    query: GetStaffCatalogItemQuery,
    repo: CatalogRepository,
) -> CatalogItemStaffDTO:
    """Retrieve single catalog item with internal metadata."""
    item = await repo.get_by_id(query.item_id)
    if item is None:
        raise EntityNotFoundError("Catalog item not found")
    return _to_staff_dto(item)


async def handle_update_draft_catalog_item(
    cmd: UpdateDraftCatalogItemCommand,
    uow: AsyncUnitOfWork,
) -> CatalogItemStaffDTO:
    """Update draft item metadata with atomic compare-and-swap on revision."""
    async with uow:
        if cmd.topic_id is not None:
            topic_exists = await uow.catalog.topic_exists(cmd.topic_id)
            if not topic_exists:
                raise InvalidDomainStateError("Unknown topic_id")

        result = await uow.catalog.update_draft_cas(
            item_id=cmd.item_id,
            expected_revision=cmd.revision,
            topic_id=cmd.topic_id,
            ci_level=cmd.ci_level,
            duration_seconds=cmd.duration_seconds,
            media_type=cmd.media_type,
            visual_support=cmd.visual_support,
            title_internal=cmd.title_internal,
        )

        if result.status == UpdateDraftResultStatus.NOT_FOUND:
            raise EntityNotFoundError("Catalog item not found")
        if result.status == UpdateDraftResultStatus.WRONG_STATUS:
            raise InvalidDomainStateError("Only draft items can be modified")
        if result.status == UpdateDraftResultStatus.REVISION_CONFLICT:
            raise ConflictError("Revision conflict: item was modified by another user")

        assert result.item is not None
        await uow.commit()

    return _to_staff_dto(result.item)


async def handle_review_catalog(item_id: str, decision: str, notes: str, reviewer_id: str, uow: AsyncUnitOfWork) -> CatalogItemStaffDTO:
    from datetime import datetime, UTC
    from jplearn_api.domain.catalog import CatalogReview

    async with uow:
        item = await uow.catalog.get_by_id_for_update(item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        if item.status != "level_qa":
            raise InvalidDomainStateError("Only level_qa items can be reviewed")
        if any(r.qa_round == item.qa_round for r in item.reviews):
            raise InvalidDomainStateError("This QA round has already been reviewed")
        if decision not in ("approve", "reject") or (decision == "reject" and not notes.strip()):
            raise InvalidDomainStateError("Rejection requires notes")
        item.reviews.append(CatalogReview(str(uuid4()), item.qa_round, decision, notes.strip(), reviewer_id, datetime.now(UTC).replace(tzinfo=None)))
        if decision == "reject":
            item.return_to_draft()
            version = await uow.content.get_current_draft_by_catalog_item_id(item_id)
            if version is not None:
                version.unfreeze_return_to_draft()
                await uow.content.update(version)
        else:
            item.revision += 1
        await uow.catalog.update(item)
        await uow.commit()
    return _to_staff_dto(item)
