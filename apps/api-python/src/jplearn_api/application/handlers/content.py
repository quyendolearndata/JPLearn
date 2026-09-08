"""Content versioning and scene breakdown application handlers (Pure Python)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jplearn_api.application.commands import ReturnToDraftCommand, UpdateContentDraftCommand
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetPublishedContentQuery, GetStaffContentQuery
from jplearn_api.application.read_models import CatalogItemStaffDTO, ContentVersionDTO, SceneDTO
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError


def _to_dto(version: ContentVersion) -> ContentVersionDTO:
    return ContentVersionDTO(
        id=version.id,
        catalog_item_id=version.catalog_item_id,
        version_number=version.version_number,
        revision=version.revision,
        is_frozen=version.is_frozen,
        is_published=version.is_published,
        created_at=version.created_at,
        published_at=version.published_at,
        scenes=[
            SceneDTO(
                id=s.id,
                scene_index=s.scene_index,
                start_time_seconds=s.start_time_seconds,
                end_time_seconds=s.end_time_seconds,
                title_jp=s.title_jp,
                transcript_jp=s.transcript_jp,
            )
            for s in version.scenes
        ],
    )


async def handle_get_published_content(
    query: GetPublishedContentQuery,
    uow: AsyncUnitOfWork,
) -> ContentVersionDTO | None:
    """Retrieve the published content version and scene breakdown for a catalog item."""
    async with uow:
        item = await uow.catalog.get_by_id(query.catalog_item_id)
        if item is None or item.status != "published":
            raise EntityNotFoundError("Published catalog item content not found")
        version = await uow.content.get_published_by_catalog_item_id(query.catalog_item_id)
        if version is None:
            # Fallback for published items without explicit scenes
            return ContentVersionDTO(
                id="",
                catalog_item_id=query.catalog_item_id,
                version_number=1,
                revision=1,
                is_frozen=True,
                is_published=True,
                scenes=[],
            )
        return _to_dto(version)


async def handle_get_staff_content(
    query: GetStaffContentQuery,
    uow: AsyncUnitOfWork,
) -> ContentVersionDTO:
    """Retrieve the draft content version for staff editing (read-only, no silent mutation)."""
    async with uow:
        item = await uow.catalog.get_by_id(query.catalog_item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")

        version = await uow.content.get_current_draft_by_catalog_item_id(query.catalog_item_id)
        if version is None:
            max_ver = await uow.content.get_max_version_number(query.catalog_item_id)
            return ContentVersionDTO(
                id="",
                catalog_item_id=query.catalog_item_id,
                version_number=max_ver + 1,
                revision=1,
                is_frozen=item.status == "level_qa",
                is_published=False,
                scenes=[],
            )

        return _to_dto(version)


async def handle_update_content_draft(
    cmd: UpdateContentDraftCommand,
    uow: AsyncUnitOfWork,
) -> ContentVersionDTO:
    """Update draft scenes with optimistic CAS revision lock."""
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.catalog_item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        if item.status != "draft":
            raise InvalidDomainStateError("Only draft items can have content modified")

        version = await uow.content.get_current_draft_by_catalog_item_id(cmd.catalog_item_id)
        if version is None:
            max_ver = await uow.content.get_max_version_number(cmd.catalog_item_id)
            version = ContentVersion(
                id=str(uuid4()),
                catalog_item_id=cmd.catalog_item_id,
                version_number=max_ver + 1,
                revision=1,
                is_frozen=False,
                is_published=False,
                scenes=[],
            )

        new_scenes = [
            Scene(
                id=str(uuid4()),
                scene_index=s.scene_index,
                start_time_seconds=s.start_time_seconds,
                end_time_seconds=s.end_time_seconds,
                title_jp=s.title_jp,
                transcript_jp=s.transcript_jp,
            )
            for s in cmd.scenes
        ]

        version.update_scenes(
            new_scenes,
            expected_revision=cmd.version_revision,
            max_duration=item.duration_seconds,
        )

        await uow.content.save_draft(version)
        await uow.commit()

    return _to_dto(version)


async def handle_return_to_draft(
    cmd: ReturnToDraftCommand,
    uow: AsyncUnitOfWork,
) -> CatalogItemStaffDTO:
    """Return a level_qa item to draft and unfreeze its content version."""
    async with uow:
        item = await uow.catalog.get_by_id_for_update(cmd.catalog_item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")

        item.return_to_draft()
        await uow.catalog.update(item)

        draft_version = await uow.content.get_current_draft_by_catalog_item_id(cmd.catalog_item_id)
        if draft_version is not None:
            draft_version.unfreeze_return_to_draft()
            await uow.content.update(draft_version)

        await uow.commit()

    from jplearn_api.application.handlers.catalog import _to_staff_dto
    return _to_staff_dto(item)
