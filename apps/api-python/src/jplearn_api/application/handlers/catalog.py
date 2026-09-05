"""Catalog use case handlers (Pure Python)."""

from __future__ import annotations

from uuid import uuid4

from jplearn_api.application.commands import (
    ArchiveCatalogItemCommand,
    CreateCatalogItemCommand,
    PublishCatalogItemCommand,
    SubmitCatalogForQaCommand,
    UnpublishCatalogItemCommand,
)
from jplearn_api.application.ports.repositories import CatalogQueryPort, CatalogRepository
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import ListPublishedCatalogQuery
from jplearn_api.application.read_models import CatalogItemPublicDTO, CatalogItemStaffDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError, MediaInvariantError


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
    )


async def handle_create_catalog_item(
    cmd: CreateCatalogItemCommand,
    uow: AsyncUnitOfWork,
    repo: CatalogRepository,
) -> CatalogItemStaffDTO:
    """Create new catalog item in draft status."""
    topic_exists = await repo.topic_exists(cmd.topic_id)
    if not topic_exists:
        raise InvalidDomainStateError("Unknown topic_id")

    item = CatalogItem(
        id=str(uuid4()),
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

    async with uow:
        await repo.add(item)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_submit_qa(
    cmd: SubmitCatalogForQaCommand,
    uow: AsyncUnitOfWork,
    repo: CatalogRepository,
) -> CatalogItemStaffDTO:
    """Submit a draft item for QA."""
    async with uow:
        item = await repo.get_by_id(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.submit_for_qa()
        await repo.update(item)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_publish(
    cmd: PublishCatalogItemCommand,
    uow: AsyncUnitOfWork,
    repo: CatalogRepository,
    storage: StoragePort,
) -> CatalogItemStaffDTO:
    """Publish a level_qa item ensuring media presence and storage availability."""
    item = await repo.get_by_id(cmd.item_id)
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

    item.publish()

    async with uow:
        await repo.update(item)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_unpublish(
    cmd: UnpublishCatalogItemCommand,
    uow: AsyncUnitOfWork,
    repo: CatalogRepository,
) -> CatalogItemStaffDTO:
    """Unpublish a published item back to draft."""
    async with uow:
        item = await repo.get_by_id(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.unpublish()
        await repo.update(item)
        await uow.commit()

    return _to_staff_dto(item)


async def handle_archive(
    cmd: ArchiveCatalogItemCommand,
    uow: AsyncUnitOfWork,
    repo: CatalogRepository,
) -> None:
    """Archive a catalog item."""
    async with uow:
        item = await repo.get_by_id(cmd.item_id)
        if item is None:
            raise EntityNotFoundError("Catalog item not found")
        item.archive()
        await repo.update(item)
        await uow.commit()


async def handle_list_published(
    query: ListPublishedCatalogQuery,
    query_port: CatalogQueryPort,
) -> list[CatalogItemPublicDTO]:
    """Retrieve published items formatted for public consumption."""
    return await query_port.list_published(query.ci_level)
