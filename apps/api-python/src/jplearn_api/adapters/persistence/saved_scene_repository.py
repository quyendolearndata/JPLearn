"""SQLAlchemy implementation of SavedSceneRepository."""

from __future__ import annotations

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    CatalogItem as OrmCatalogItem,
)
from jplearn_api.adapters.persistence.models import (
    ContentVersion as OrmContentVersion,
)
from jplearn_api.adapters.persistence.models import (
    SavedScene as OrmSavedScene,
)
from jplearn_api.adapters.persistence.models import (
    Scene as OrmScene,
)
from jplearn_api.application.ports.repositories import (
    SavedSceneContext,
    SavedSceneProjection,
)
from jplearn_api.domain.saved_scene import SavedScene


class SqlAlchemySavedSceneRepository:
    """SQLAlchemy adapter for SavedSceneRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, scene_id: str) -> SavedScene | None:
        stmt = select(OrmSavedScene).where(
            OrmSavedScene.user_id == user_id,
            OrmSavedScene.scene_id == scene_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return SavedScene(
            id=orm.id,
            user_id=orm.user_id,
            scene_id=orm.scene_id,
            saved_at=orm.saved_at,
        )

    async def add(self, saved_scene: SavedScene) -> None:
        orm = OrmSavedScene(
            id=saved_scene.id,
            user_id=saved_scene.user_id,
            scene_id=saved_scene.scene_id,
            saved_at=saved_scene.saved_at,
        )
        self._session.add(orm)

    async def delete(self, user_id: str, scene_id: str) -> bool:
        stmt = delete(OrmSavedScene).where(
            OrmSavedScene.user_id == user_id,
            OrmSavedScene.scene_id == scene_id,
        )
        result = await self._session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)

    async def get_scene_context(self, scene_id: str) -> SavedSceneContext | None:
        stmt = (
            select(
                OrmScene.id.label("scene_id"),
                OrmContentVersion.id.label("content_version_id"),
                OrmContentVersion.is_published.label("is_version_published"),
                OrmCatalogItem.id.label("catalog_item_id"),
                OrmCatalogItem.status.label("catalog_status"),
            )
            .join(OrmContentVersion, OrmScene.content_version_id == OrmContentVersion.id)
            .join(OrmCatalogItem, OrmContentVersion.catalog_item_id == OrmCatalogItem.id)
            .where(OrmScene.id == scene_id)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if not row:
            return None

        latest_v_stmt = (
            select(OrmContentVersion.id)
            .where(
                OrmContentVersion.catalog_item_id == row.catalog_item_id,
                OrmContentVersion.is_published.is_(True),
            )
            .order_by(desc(OrmContentVersion.version_number))
            .limit(1)
        )
        latest_v_res = await self._session.execute(latest_v_stmt)
        latest_published_v_id = latest_v_res.scalar_one_or_none()

        is_current_published = latest_published_v_id is not None and latest_published_v_id == row.content_version_id

        return SavedSceneContext(
            scene_id=row.scene_id,
            content_version_id=row.content_version_id,
            is_version_published=row.is_version_published,
            catalog_item_id=row.catalog_item_id,
            catalog_status=row.catalog_status,
            is_current_published_version=is_current_published,
        )

    async def list_projections_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[SavedSceneProjection], int]:
        count_stmt = select(func.count(OrmSavedScene.id)).where(OrmSavedScene.user_id == user_id)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(
                OrmSavedScene.id.label("saved_scene_id"),
                OrmSavedScene.scene_id.label("scene_id"),
                OrmSavedScene.saved_at.label("saved_at"),
                OrmScene.scene_index,
                OrmScene.start_time_seconds,
                OrmScene.end_time_seconds,
                OrmScene.title_jp,
                OrmScene.transcript_jp,
                OrmContentVersion.id.label("content_version_id"),
                OrmContentVersion.is_published.label("is_version_published"),
                OrmCatalogItem.id.label("catalog_item_id"),
                OrmCatalogItem.status.label("catalog_status"),
            )
            .outerjoin(OrmScene, OrmSavedScene.scene_id == OrmScene.id)
            .outerjoin(OrmContentVersion, OrmScene.content_version_id == OrmContentVersion.id)
            .outerjoin(OrmCatalogItem, OrmContentVersion.catalog_item_id == OrmCatalogItem.id)
            .where(OrmSavedScene.user_id == user_id)
            .order_by(desc(OrmSavedScene.saved_at), desc(OrmSavedScene.id))
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()

        catalog_ids = {r.catalog_item_id for r in rows if r.catalog_item_id}
        latest_versions: dict[str, str] = {}
        if catalog_ids:
            subq = (
                select(
                    OrmContentVersion.catalog_item_id,
                    OrmContentVersion.id,
                    func.row_number()
                    .over(
                        partition_by=OrmContentVersion.catalog_item_id,
                        order_by=desc(OrmContentVersion.version_number),
                    )
                    .label("rn"),
                )
                .where(
                    OrmContentVersion.catalog_item_id.in_(catalog_ids),
                    OrmContentVersion.is_published.is_(True),
                )
                .subquery()
            )
            latest_stmt = select(subq.c.catalog_item_id, subq.c.id).where(subq.c.rn == 1)
            latest_res = await self._session.execute(latest_stmt)
            for cat_id, ver_id in latest_res.all():
                latest_versions[cat_id] = ver_id

        projections: list[SavedSceneProjection] = []
        for r in rows:
            if r.catalog_item_id is None or r.catalog_status != "published":
                availability = "unavailable"
                reason = "catalog_unpublished" if r.catalog_status else "scene_not_found"
                projections.append(
                    SavedSceneProjection(
                        id=r.saved_scene_id,
                        scene_id=r.scene_id,
                        saved_at=r.saved_at,
                        availability=availability,
                        unavailable_reason=reason,
                        catalog_item_id=None,
                        content_version_id=None,
                        scene_index=None,
                        start_time_seconds=None,
                        end_time_seconds=None,
                        title_jp=None,
                        transcript_jp=None,
                    )
                )
            elif not r.is_version_published:
                availability = "unavailable"
                reason = "version_unpublished"
                projections.append(
                    SavedSceneProjection(
                        id=r.saved_scene_id,
                        scene_id=r.scene_id,
                        saved_at=r.saved_at,
                        availability=availability,
                        unavailable_reason=reason,
                        catalog_item_id=None,
                        content_version_id=None,
                        scene_index=None,
                        start_time_seconds=None,
                        end_time_seconds=None,
                        title_jp=None,
                        transcript_jp=None,
                    )
                )
            else:
                latest_v_id = latest_versions.get(r.catalog_item_id)
                if latest_v_id == r.content_version_id:
                    availability = "available"
                else:
                    availability = "stale_version"
                projections.append(
                    SavedSceneProjection(
                        id=r.saved_scene_id,
                        scene_id=r.scene_id,
                        saved_at=r.saved_at,
                        availability=availability,
                        unavailable_reason=None,
                        catalog_item_id=r.catalog_item_id,
                        content_version_id=r.content_version_id,
                        scene_index=r.scene_index,
                        start_time_seconds=r.start_time_seconds,
                        end_time_seconds=r.end_time_seconds,
                        title_jp=r.title_jp,
                        transcript_jp=r.transcript_jp,
                    )
                )

        return projections, total
