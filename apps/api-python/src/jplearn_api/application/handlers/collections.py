"""Application handlers for Personal Collections (UC-L23)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from jplearn_api.application.commands import (
    CreateCollectionCommand,
    DeleteCollectionCommand,
    PatchCollectionCommand,
    UpdateCollectionScenesCommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetCollectionQuery, ListCollectionsQuery
from jplearn_api.domain.collection import CollectionDetail, PersonalCollection
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
)

MAX_COLLECTIONS_PER_USER = 50
MAX_SCENES_PER_COLLECTION = 200


async def handle_create_collection(
    command: CreateCollectionCommand,
    uow: AsyncUnitOfWork,
) -> tuple[PersonalCollection, bool]:
    """Create a new private collection for the user with optional idempotency."""
    name = command.name.strip()
    if not name or len(name) > 80:
        raise InvalidDomainStateError("Collection name must be between 1 and 80 characters.")

    req_hash = hashlib.sha256(name.encode("utf-8")).hexdigest() if command.idempotency_key else None

    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)

        # Idempotency replay check
        if command.idempotency_key:
            existing = await uow.collections.find_by_idempotency_key(command.user_id, command.idempotency_key)
            if existing:
                coll, stored_hash = existing
                if stored_hash == req_hash:
                    return coll, False
                raise ConflictError("Idempotency key reused with different collection name.")

        # Quota check
        count = await uow.collections.count_by_user(command.user_id)
        if count >= MAX_COLLECTIONS_PER_USER:
            raise InvalidDomainStateError(f"Maximum limit of {MAX_COLLECTIONS_PER_USER} collections reached.")

        now = datetime.now(UTC)
        new_coll = PersonalCollection(
            id=str(uuid4()),
            user_id=command.user_id,
            name=name,
            revision=1,
            created_at=now,
            updated_at=now,
            scene_count=0,
        )
        created = await uow.collections.create(
            new_coll,
            idempotency_key=command.idempotency_key,
            request_hash=req_hash,
        )
        await uow.commit()
        return created, True


async def handle_list_collections(
    query: ListCollectionsQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[PersonalCollection], int]:
    """List personal collections owned by the user with pagination."""
    async with uow:
        return await uow.collections.list_by_user(
            user_id=query.user_id,
            offset=query.offset,
            limit=query.limit,
        )


async def handle_get_collection(
    query: GetCollectionQuery,
    uow: AsyncUnitOfWork,
) -> CollectionDetail:
    """Get full details of a personal collection including ordered scenes and availability."""
    async with uow:
        detail = await uow.collections.get_detail(
            user_id=query.user_id,
            collection_id=query.collection_id,
        )
        if not detail:
            raise EntityNotFoundError(f"Collection {query.collection_id} not found")
        return detail


async def handle_patch_collection(
    command: PatchCollectionCommand,
    uow: AsyncUnitOfWork,
) -> PersonalCollection:
    """Update collection name with OCC expected_revision check."""
    name = command.name.strip()
    if not name or len(name) > 80:
        raise InvalidDomainStateError("Collection name must be between 1 and 80 characters.")

    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)
        updated = await uow.collections.update_name(
            user_id=command.user_id,
            collection_id=command.collection_id,
            expected_revision=command.expected_revision,
            new_name=name,
        )
        await uow.commit()
        return updated


async def handle_update_collection_scenes(
    command: UpdateCollectionScenesCommand,
    uow: AsyncUnitOfWork,
) -> PersonalCollection:
    """Replace all scenes in the collection with order and OCC check."""
    if len(command.scene_ids) > MAX_SCENES_PER_COLLECTION:
        raise InvalidDomainStateError(f"Maximum of {MAX_SCENES_PER_COLLECTION} scenes allowed per collection.")
    if len(command.scene_ids) != len(set(command.scene_ids)):
        raise InvalidDomainStateError("Duplicate scenes are not allowed in a collection.")

    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)

        # 1. Check collection existence and revision
        existing = await uow.collections.get_by_id(command.user_id, command.collection_id)
        if not existing:
            raise EntityNotFoundError(f"Collection {command.collection_id} not found")
        if existing.revision != command.expected_revision:
            raise ConflictError(
                f"Collection revision conflict: expected {command.expected_revision}, current {existing.revision}"
            )

        # 2. Verify all scenes are currently saved by the user
        for sid in command.scene_ids:
            saved = await uow.saved_scenes.get(command.user_id, sid)
            if not saved:
                raise InvalidDomainStateError(
                    f"Scene {sid} is not saved. All scenes must be saved before adding to a collection."
                )

        # 3. Check stale/unavailable for newly added scenes
        curr_detail = await uow.collections.get_detail(command.user_id, command.collection_id)
        existing_scene_ids = {s.scene_id for s in curr_detail.scenes} if curr_detail else set()
        for sid in command.scene_ids:
            if sid not in existing_scene_ids:
                ctx = await uow.saved_scenes.get_scene_context(sid)
                if (
                    not ctx
                    or not ctx.is_version_published
                    or ctx.catalog_status != "published"
                    or not ctx.is_current_published_version
                ):
                    raise InvalidDomainStateError(f"Cannot add stale or unavailable scene {sid} to a collection.")

        updated = await uow.collections.replace_scenes(
            user_id=command.user_id,
            collection_id=command.collection_id,
            expected_revision=command.expected_revision,
            scene_ids=command.scene_ids,
        )
        await uow.commit()
        return updated


async def handle_delete_collection(
    command: DeleteCollectionCommand,
    uow: AsyncUnitOfWork,
) -> None:
    """Delete a personal collection idempotently."""
    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)
        await uow.collections.delete(
            user_id=command.user_id,
            collection_id=command.collection_id,
        )
        await uow.commit()
