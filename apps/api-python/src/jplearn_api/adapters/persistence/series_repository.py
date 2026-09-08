"""SQLAlchemy implementation of SeriesRepository."""

from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.adapters.persistence.models import (
    CatalogItem as OrmCatalogItem,
)
from jplearn_api.adapters.persistence.models import (
    Series as OrmSeries,
)
from jplearn_api.adapters.persistence.models import (
    SeriesItem as OrmSeriesItem,
)
from jplearn_api.domain.series import Series, SeriesItem


def _to_domain(orm: OrmSeries) -> Series:
    items = [
        SeriesItem(
            catalog_item_id=it.catalog_item_id,
            position=it.position,
        )
        for it in sorted(orm.items, key=lambda x: x.position)
    ]
    return Series(
        id=orm.id,
        title=orm.title,
        description=orm.description,
        ci_level=orm.ci_level,
        topic_id=orm.topic_id,
        status=orm.status,
        revision=orm.revision,
        items=items,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemySeriesRepository:
    """SQLAlchemy adapter for SeriesRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, series_id: str) -> Series | None:
        stmt = select(OrmSeries).options(selectinload(OrmSeries.items)).where(OrmSeries.id == series_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_id_for_update(self, series_id: str) -> Series | None:
        stmt = (
            select(OrmSeries).options(selectinload(OrmSeries.items)).where(OrmSeries.id == series_id).with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def add(self, series: Series) -> None:
        orm = OrmSeries(
            id=series.id,
            title=series.title,
            description=series.description,
            ci_level=series.ci_level,
            topic_id=series.topic_id,
            status=series.status,
            revision=series.revision,
            created_at=series.created_at,
            updated_at=series.updated_at,
        )
        self._session.add(orm)
        for item in series.items:
            orm_item = OrmSeriesItem(
                series_id=series.id,
                catalog_item_id=item.catalog_item_id,
                position=item.position,
            )
            self._session.add(orm_item)

    async def update(self, series: Series) -> None:
        stmt = select(OrmSeries).options(selectinload(OrmSeries.items)).where(OrmSeries.id == series.id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one()

        orm.title = series.title
        orm.description = series.description
        orm.ci_level = series.ci_level
        orm.topic_id = series.topic_id
        orm.status = series.status
        orm.revision = series.revision
        orm.updated_at = series.updated_at

        # Replace items
        await self._session.execute(delete(OrmSeriesItem).where(OrmSeriesItem.series_id == series.id))
        for item in series.items:
            orm_item = OrmSeriesItem(
                series_id=series.id,
                catalog_item_id=item.catalog_item_id,
                position=item.position,
            )
            self._session.add(orm_item)

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Series]:
        stmt = select(OrmSeries).options(selectinload(OrmSeries.items))
        if status:
            stmt = stmt.where(OrmSeries.status == status)
        if ci_level:
            stmt = stmt.where(OrmSeries.ci_level == ci_level)
        if topic_id:
            stmt = stmt.where(OrmSeries.topic_id == topic_id)
        stmt = stmt.order_by(desc(OrmSeries.created_at)).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_domain(orm) for orm in result.scalars().all()]

    async def list_published(
        self,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Series]:
        stmt = select(OrmSeries).options(selectinload(OrmSeries.items)).where(OrmSeries.status == "published")
        if ci_level:
            stmt = stmt.where(OrmSeries.ci_level == ci_level)
        if topic_id:
            stmt = stmt.where(OrmSeries.topic_id == topic_id)
        stmt = stmt.order_by(desc(OrmSeries.created_at)).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_domain(orm) for orm in result.scalars().all()]

    async def get_published_catalog_item_ids(self, item_ids: list[str]) -> set[str]:
        if not item_ids:
            return set()
        stmt = select(OrmCatalogItem.id).where(
            OrmCatalogItem.id.in_(item_ids),
            OrmCatalogItem.status == "published",
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())
