"""Application handlers for Saved Scenes (bookmarks)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jplearn_api.application.commands import DeleteSavedSceneCommand, SaveSceneCommand
from jplearn_api.application.ports.repositories import SavedSceneProjection
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import ListSavedScenesQuery
from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError
from jplearn_api.domain.saved_scene import SavedScene


async def handle_save_scene(
    command: SaveSceneCommand,
    uow: AsyncUnitOfWork,
) -> tuple[SavedScene, bool]:
    """Save a scene from a published current version of a published catalog item.

    Returns (saved_scene, created). If already saved, created=False (idempotent).
    """
    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)
        ctx = await uow.saved_scenes.get_scene_context(command.scene_id)
        if ctx is None:
            raise EntityNotFoundError(f"Scene {command.scene_id} not found")
        if not ctx.is_version_published:
            raise InvalidDomainStateError("Cannot save scene from unpublished content version")
        if ctx.catalog_status != "published":
            raise InvalidDomainStateError("Cannot save scene from unpublished catalog item")
        if not ctx.is_current_published_version:
            raise InvalidDomainStateError("Cannot save scene from outdated content version")

        existing = await uow.saved_scenes.get(command.user_id, command.scene_id)
        if existing:
            return existing, False

        saved_scene = SavedScene(
            id=str(uuid4()),
            user_id=command.user_id,
            scene_id=command.scene_id,
            saved_at=datetime.now(timezone.utc),
        )
        await uow.saved_scenes.add(saved_scene)
        await uow.commit()
        return saved_scene, True


async def handle_delete_saved_scene(
    command: DeleteSavedSceneCommand,
    uow: AsyncUnitOfWork,
) -> None:
    """Delete a saved scene idempotently (204 No Content)."""
    async with uow:
        await uow.collections.acquire_library_lock(command.user_id)
        await uow.collections.bump_revisions_for_scenes(command.user_id, [command.scene_id])
        await uow.saved_scenes.delete(command.user_id, command.scene_id)
        await uow.commit()


async def handle_list_saved_scenes(
    query: ListSavedScenesQuery,
    uow: AsyncUnitOfWork,
) -> tuple[list[SavedSceneProjection], int]:
    """List saved scenes for a user with availability projections and pagination."""
    async with uow:
        return await uow.saved_scenes.list_projections_by_user(
            user_id=query.user_id,
            offset=query.offset,
            limit=query.limit,
        )
