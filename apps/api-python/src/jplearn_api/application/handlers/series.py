"""Series application handlers implementing staff editing and learner viewing."""

from __future__ import annotations

from uuid import uuid4

from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError
from jplearn_api.domain.series import Series


async def handle_create_series(
    uow: AsyncUnitOfWork,
    title: str,
    description: str,
    ci_level: str,
    topic_id: str,
) -> Series:
    """Create a new series in draft status."""
    clean_title = title.strip()
    if not clean_title:
        raise InvalidDomainStateError("Series title must not be empty")

    async with uow:
        topic_exists = await uow.catalog.topic_exists(topic_id)
        if not topic_exists:
            raise InvalidDomainStateError(f"Topic '{topic_id}' does not exist")

        series = Series(
            id=str(uuid4()),
            title=clean_title,
            description=description.strip(),
            ci_level=str(ci_level),
            topic_id=topic_id,
            status="draft",
            revision=1,
            items=[],
        )
        await uow.series.add(series)
        await uow.commit()
        return series


async def handle_get_staff_series(
    uow: AsyncUnitOfWork,
    series_id: str,
) -> Series:
    """Fetch series details for staff editing, including all constituent clips."""
    async with uow:
        series = await uow.series.get_by_id(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")
        return series


async def handle_list_staff_series(
    uow: AsyncUnitOfWork,
    status: str | None = None,
    ci_level: str | None = None,
    topic_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Series]:
    """List series with filtering for staff management."""
    async with uow:
        return await uow.series.list_staff(
            status=status,
            ci_level=ci_level,
            topic_id=topic_id,
            offset=offset,
            limit=limit,
        )


async def handle_update_series_metadata(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
    title: str | None = None,
    description: str | None = None,
    ci_level: str | None = None,
    topic_id: str | None = None,
) -> Series:
    """Update series metadata with optimistic revision check."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        if topic_id is not None:
            topic_exists = await uow.catalog.topic_exists(topic_id)
            if not topic_exists:
                raise InvalidDomainStateError(f"Topic '{topic_id}' does not exist")

        series.update_metadata(
            expected_revision=expected_revision,
            title=title,
            description=description,
            ci_level=ci_level,
            topic_id=topic_id,
        )
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_update_series_items(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
    item_ids: list[str],
) -> Series:
    """Replace the ordered list of items in the series."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        for item_id in item_ids:
            catalog_item = await uow.catalog.get_by_id(item_id)
            if not catalog_item:
                raise InvalidDomainStateError(f"Catalog item '{item_id}' does not exist")

        series.update_items(expected_revision=expected_revision, catalog_item_ids=item_ids)
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_submit_series_qa(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
) -> Series:
    """Transition series from draft to level_qa."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        series.submit_qa(expected_revision=expected_revision)
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_return_series_to_draft(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
    reason: str = "",
) -> Series:
    """Transition series from level_qa back to draft."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        series.return_to_draft(expected_revision=expected_revision, reason=reason)
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_publish_series(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
) -> Series:
    """Publish series ensuring all constituent items are currently published."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        constituent_ids = [it.catalog_item_id for it in series.items]
        published_ids = await uow.series.get_published_catalog_item_ids(constituent_ids)

        series.publish(expected_revision=expected_revision, published_catalog_ids=published_ids)
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_unpublish_series(
    uow: AsyncUnitOfWork,
    series_id: str,
    expected_revision: int,
) -> Series:
    """Unpublish series from learner view."""
    async with uow:
        series = await uow.series.get_by_id_for_update(series_id)
        if not series:
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        series.unpublish(expected_revision=expected_revision)
        await uow.series.update(series)
        await uow.commit()
        return series


async def handle_list_learner_series(
    uow: AsyncUnitOfWork,
    ci_level: str | None = None,
    topic_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[tuple[Series, int]]:
    """List published series for learners, filtering out series with 0 available published clips."""
    async with uow:
        published_series = await uow.series.list_published(
            ci_level=ci_level,
            topic_id=topic_id,
            offset=offset,
            limit=limit,
        )
        results: list[tuple[Series, int]] = []
        for s in published_series:
            constituent_ids = [it.catalog_item_id for it in s.items]
            published_ids = await uow.series.get_published_catalog_item_ids(constituent_ids)
            available_count = len([it for it in s.items if it.catalog_item_id in published_ids])
            if available_count > 0:
                results.append((s, available_count))
        return results


async def handle_get_learner_series(
    uow: AsyncUnitOfWork,
    series_id: str,
) -> tuple[Series, list[dict]]:
    """Get published series for learner, returning only currently published clips.

    If series does not exist, is not published, or has 0 available clips, returns 404.
    """
    async with uow:
        series = await uow.series.get_by_id(series_id)
        if not series or series.status != "published":
            raise EntityNotFoundError(f"Series '{series_id}' not found")

        constituent_ids = [it.catalog_item_id for it in series.items]
        published_ids = await uow.series.get_published_catalog_item_ids(constituent_ids)

        available_items = [it for it in series.items if it.catalog_item_id in published_ids]
        if not available_items:
            raise EntityNotFoundError(f"Series '{series_id}' has no available items")

        # Load catalog item metadata for each available clip
        clips_metadata: list[dict] = []
        for it in available_items:
            catalog_item = await uow.catalog.get_by_id(it.catalog_item_id)
            if catalog_item:
                clips_metadata.append(
                    {
                        "catalog_item_id": catalog_item.id,
                        "position": it.position,
                        "topic_id": catalog_item.topic_id,
                        "ci_level": str(catalog_item.ci_level),
                        "duration_seconds": catalog_item.duration_seconds,
                    }
                )

        return series, clips_metadata
