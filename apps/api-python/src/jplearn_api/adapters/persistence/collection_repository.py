"""SQLAlchemy implementation of CollectionRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import delete, desc, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    CatalogItem as OrmCatalogItem,
    CollectionScene as OrmCollectionScene,
    ContentVersion as OrmContentVersion,
    PersonalCollection as OrmPersonalCollection,
    Scene as OrmScene,
)
from jplearn_api.domain.collection import (
    CollectionDetail,
    CollectionSceneDetail,
    PersonalCollection,
)
from jplearn_api.domain.errors import ConflictError, EntityNotFoundError
from jplearn_api.domain.saved_scene import SceneAvailability


class SqlAlchemyCollectionRepository:
    """SQLAlchemy adapter for CollectionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def acquire_library_lock(self, user_id: str) -> None:
        """Lock the library state for a user to serialize modifications."""
        await self._session.execute(
            text(
                """
                INSERT INTO learner_library_state (user_id, collection_count, updated_at)
                VALUES (:user_id, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"user_id": user_id},
        )
        await self._session.execute(
            text("SELECT user_id FROM learner_library_state WHERE user_id = :user_id FOR UPDATE"),
            {"user_id": user_id},
        )

    async def get_by_id(self, user_id: str, collection_id: str) -> PersonalCollection | None:
        stmt = (
            select(
                OrmPersonalCollection,
                func.count(OrmCollectionScene.position).label("scene_count"),
            )
            .outerjoin(
                OrmCollectionScene,
                OrmPersonalCollection.id == OrmCollectionScene.collection_id,
            )
            .where(
                OrmPersonalCollection.id == collection_id,
                OrmPersonalCollection.user_id == user_id,
            )
            .group_by(OrmPersonalCollection.id)
        )
        res = await self._session.execute(stmt)
        row = res.first()
        if not row:
            return None
        orm_coll, count = row
        return PersonalCollection(
            id=orm_coll.id,
            user_id=orm_coll.user_id,
            name=orm_coll.name,
            revision=orm_coll.revision,
            created_at=orm_coll.created_at,
            updated_at=orm_coll.updated_at,
            scene_count=count or 0,
        )

    async def get_detail(self, user_id: str, collection_id: str) -> CollectionDetail | None:
        # 1. Fetch collection
        coll_stmt = select(OrmPersonalCollection).where(
            OrmPersonalCollection.id == collection_id,
            OrmPersonalCollection.user_id == user_id,
        )
        res = await self._session.execute(coll_stmt)
        orm_coll = res.scalar_one_or_none()
        if not orm_coll:
            return None

        # 2. Fetch scenes with catalog context
        scenes_stmt = (
            select(
                OrmCollectionScene.position,
                OrmCollectionScene.scene_id,
                OrmCollectionScene.added_at,
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
            .outerjoin(OrmScene, OrmCollectionScene.scene_id == OrmScene.id)
            .outerjoin(OrmContentVersion, OrmScene.content_version_id == OrmContentVersion.id)
            .outerjoin(OrmCatalogItem, OrmContentVersion.catalog_item_id == OrmCatalogItem.id)
            .where(
                OrmCollectionScene.collection_id == collection_id,
                OrmCollectionScene.user_id == user_id,
            )
            .order_by(OrmCollectionScene.position.asc())
        )
        rows = (await self._session.execute(scenes_stmt)).all()

        # 3. Determine current published content versions
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

        # 4. Build scene details
        scene_details: list[CollectionSceneDetail] = []
        for r in rows:
            if r.catalog_item_id is None or r.catalog_status != "published":
                scene_details.append(
                    CollectionSceneDetail(
                        position=r.position,
                        scene_id=r.scene_id,
                        availability=SceneAvailability.UNAVAILABLE,
                        scene=None,
                        reason="catalog_unpublished" if r.catalog_status else "scene_not_found",
                        added_at=r.added_at,
                    )
                )
            elif not r.is_version_published or latest_versions.get(r.catalog_item_id) != r.content_version_id:
                scene_details.append(
                    CollectionSceneDetail(
                        position=r.position,
                        scene_id=r.scene_id,
                        availability=SceneAvailability.STALE_VERSION,
                        scene={
                            "catalog_item_id": r.catalog_item_id,
                            "content_version_id": r.content_version_id,
                            "scene_index": r.scene_index,
                            "start_time_seconds": r.start_time_seconds,
                            "end_time_seconds": r.end_time_seconds,
                            "title_jp": r.title_jp,
                            "transcript_jp": r.transcript_jp,
                        },
                        reason="new_version_available",
                        added_at=r.added_at,
                    )
                )
            else:
                scene_details.append(
                    CollectionSceneDetail(
                        position=r.position,
                        scene_id=r.scene_id,
                        availability=SceneAvailability.AVAILABLE,
                        scene={
                            "catalog_item_id": r.catalog_item_id,
                            "content_version_id": r.content_version_id,
                            "scene_index": r.scene_index,
                            "start_time_seconds": r.start_time_seconds,
                            "end_time_seconds": r.end_time_seconds,
                            "title_jp": r.title_jp,
                            "transcript_jp": r.transcript_jp,
                        },
                        reason=None,
                        added_at=r.added_at,
                    )
                )

        return CollectionDetail(
            id=orm_coll.id,
            user_id=orm_coll.user_id,
            name=orm_coll.name,
            revision=orm_coll.revision,
            scene_count=len(scene_details),
            created_at=orm_coll.created_at,
            updated_at=orm_coll.updated_at,
            scenes=scene_details,
        )

    async def find_by_idempotency_key(
        self, user_id: str, key: str
    ) -> tuple[PersonalCollection, str | None] | None:
        stmt = (
            select(
                OrmPersonalCollection,
                func.count(OrmCollectionScene.position).label("scene_count"),
            )
            .outerjoin(
                OrmCollectionScene,
                OrmPersonalCollection.id == OrmCollectionScene.collection_id,
            )
            .where(
                OrmPersonalCollection.user_id == user_id,
                OrmPersonalCollection.idempotency_key == key,
            )
            .group_by(OrmPersonalCollection.id)
        )
        res = await self._session.execute(stmt)
        row = res.first()
        if not row:
            return None
        orm_coll, count = row
        coll = PersonalCollection(
            id=orm_coll.id,
            user_id=orm_coll.user_id,
            name=orm_coll.name,
            revision=orm_coll.revision,
            created_at=orm_coll.created_at,
            updated_at=orm_coll.updated_at,
            scene_count=count or 0,
        )
        return coll, orm_coll.request_hash

    async def count_by_user(self, user_id: str) -> int:
        stmt = select(func.count(OrmPersonalCollection.id)).where(
            OrmPersonalCollection.user_id == user_id
        )
        res = await self._session.execute(stmt)
        return res.scalar() or 0

    async def create(
        self,
        collection: PersonalCollection,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> PersonalCollection:
        orm = OrmPersonalCollection(
            id=collection.id,
            user_id=collection.user_id,
            name=collection.name,
            revision=collection.revision,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )
        self._session.add(orm)
        await self._session.flush()

        # Update library state count
        await self._session.execute(
            text(
                """
                UPDATE learner_library_state
                SET collection_count = collection_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id
                """
            ),
            {"user_id": collection.user_id},
        )
        return collection

    async def list_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PersonalCollection], int]:
        count_stmt = select(func.count(OrmPersonalCollection.id)).where(
            OrmPersonalCollection.user_id == user_id
        )
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(
                OrmPersonalCollection,
                func.count(OrmCollectionScene.position).label("scene_count"),
            )
            .outerjoin(
                OrmCollectionScene,
                OrmPersonalCollection.id == OrmCollectionScene.collection_id,
            )
            .where(OrmPersonalCollection.user_id == user_id)
            .group_by(OrmPersonalCollection.id)
            .order_by(
                desc(OrmPersonalCollection.created_at),
                desc(OrmPersonalCollection.id),
            )
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        collections: list[PersonalCollection] = []
        for orm_coll, count in rows:
            collections.append(
                PersonalCollection(
                    id=orm_coll.id,
                    user_id=orm_coll.user_id,
                    name=orm_coll.name,
                    revision=orm_coll.revision,
                    created_at=orm_coll.created_at,
                    updated_at=orm_coll.updated_at,
                    scene_count=count or 0,
                )
            )
        return collections, total

    async def update_name(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        new_name: str,
    ) -> PersonalCollection:
        stmt = (
            update(OrmPersonalCollection)
            .where(
                OrmPersonalCollection.id == collection_id,
                OrmPersonalCollection.user_id == user_id,
                OrmPersonalCollection.revision == expected_revision,
            )
            .values(
                name=new_name,
                revision=OrmPersonalCollection.revision + 1,
                updated_at=func.current_timestamp(),
            )
            .returning(OrmPersonalCollection)
        )
        res = await self._session.execute(stmt)
        orm_coll = res.scalar_one_or_none()
        if not orm_coll:
            # Check if it exists with another revision
            check_stmt = select(OrmPersonalCollection.revision).where(
                OrmPersonalCollection.id == collection_id,
                OrmPersonalCollection.user_id == user_id,
            )
            actual_rev = (await self._session.execute(check_stmt)).scalar_one_or_none()
            if actual_rev is not None:
                raise ConflictError(
                    f"Collection revision conflict: expected {expected_revision}, current {actual_rev}"
                )
            raise EntityNotFoundError(f"Collection {collection_id} not found")

        # Get scene count
        count_stmt = select(func.count(OrmCollectionScene.position)).where(
            OrmCollectionScene.collection_id == collection_id,
            OrmCollectionScene.user_id == user_id,
        )
        scene_count = (await self._session.execute(count_stmt)).scalar() or 0

        return PersonalCollection(
            id=orm_coll.id,
            user_id=orm_coll.user_id,
            name=orm_coll.name,
            revision=orm_coll.revision,
            created_at=orm_coll.created_at,
            updated_at=orm_coll.updated_at,
            scene_count=scene_count,
        )

    async def replace_scenes(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        scene_ids: list[str],
    ) -> PersonalCollection:
        # Check OCC revision
        check_stmt = select(OrmPersonalCollection).where(
            OrmPersonalCollection.id == collection_id,
            OrmPersonalCollection.user_id == user_id,
        )
        orm_coll = (await self._session.execute(check_stmt)).scalar_one_or_none()
        if not orm_coll:
            raise EntityNotFoundError(f"Collection {collection_id} not found")
        if orm_coll.revision != expected_revision:
            raise ConflictError(
                f"Collection revision conflict: expected {expected_revision}, current {orm_coll.revision}"
            )

        # Delete existing scenes
        del_stmt = delete(OrmCollectionScene).where(
            OrmCollectionScene.collection_id == collection_id,
            OrmCollectionScene.user_id == user_id,
        )
        await self._session.execute(del_stmt)

        # Insert new scenes
        now = datetime.now(timezone.utc)
        for pos, scene_id in enumerate(scene_ids):
            self._session.add(
                OrmCollectionScene(
                    collection_id=collection_id,
                    user_id=user_id,
                    scene_id=scene_id,
                    position=pos,
                    added_at=now,
                )
            )

        # Bump revision
        orm_coll.revision += 1
        orm_coll.updated_at = now
        await self._session.flush()

        return PersonalCollection(
            id=orm_coll.id,
            user_id=orm_coll.user_id,
            name=orm_coll.name,
            revision=orm_coll.revision,
            created_at=orm_coll.created_at,
            updated_at=orm_coll.updated_at,
            scene_count=len(scene_ids),
        )

    async def delete(self, user_id: str, collection_id: str) -> bool:
        stmt = delete(OrmPersonalCollection).where(
            OrmPersonalCollection.id == collection_id,
            OrmPersonalCollection.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        if res.rowcount and res.rowcount > 0:
            await self._session.execute(
                text(
                    """
                    UPDATE learner_library_state
                    SET collection_count = GREATEST(0, collection_count - 1), updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
            return True
        return False

    async def bump_revisions_for_scenes(self, user_id: str, scene_ids: list[str]) -> list[str]:
        if not scene_ids:
            return []
        stmt = (
            select(OrmCollectionScene.collection_id)
            .where(
                OrmCollectionScene.user_id == user_id,
                OrmCollectionScene.scene_id.in_(scene_ids),
            )
            .distinct()
        )
        res = await self._session.execute(stmt)
        affected_ids = [r[0] for r in res.all()]
        if affected_ids:
            upd = (
                update(OrmPersonalCollection)
                .where(
                    OrmPersonalCollection.id.in_(affected_ids),
                    OrmPersonalCollection.user_id == user_id,
                )
                .values(
                    revision=OrmPersonalCollection.revision + 1,
                    updated_at=func.current_timestamp(),
                )
            )
            await self._session.execute(upd)
        return affected_ids
