"""SQLAlchemy implementation of ContentRepository."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.adapters.persistence.models import (
    ContentVersion as OrmContentVersion,
)
from jplearn_api.adapters.persistence.models import (
    Scene as OrmScene,
)
from jplearn_api.domain.content import ContentVersion, Scene


def _to_domain(orm: OrmContentVersion) -> ContentVersion:
    scenes = [
        Scene(
            id=s.id,
            scene_index=s.scene_index,
            start_time_seconds=s.start_time_seconds,
            end_time_seconds=s.end_time_seconds,
            title_jp=s.title_jp,
            transcript_jp=s.transcript_jp,
        )
        for s in sorted(orm.scenes, key=lambda x: x.scene_index)
    ]
    return ContentVersion(
        id=orm.id,
        catalog_item_id=orm.catalog_item_id,
        version_number=orm.version_number,
        revision=orm.revision,
        is_frozen=orm.is_frozen,
        is_published=orm.is_published,
        created_at=orm.created_at,
        published_at=orm.published_at,
        scenes=scenes,
        media_asset_id=orm.media_asset_id,
        media_storage_key=orm.media_storage_key,
        media_hls_url=orm.media_hls_url,
        duration_seconds=orm.duration_seconds,
        duration_source=orm.duration_source,
        source_sha256=orm.source_sha256,
        measured_duration_ms=orm.measured_duration_ms,
        hls_bundle_sha256=orm.hls_bundle_sha256,
    )


class SqlAlchemyContentRepository:
    """SQLAlchemy adapter for ContentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_published_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None:
        stmt = (
            select(OrmContentVersion)
            .options(selectinload(OrmContentVersion.scenes))
            .where(
                OrmContentVersion.catalog_item_id == catalog_item_id,
                OrmContentVersion.is_published.is_(True),
            )
            .order_by(desc(OrmContentVersion.version_number))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_current_draft_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None:
        stmt = (
            select(OrmContentVersion)
            .options(selectinload(OrmContentVersion.scenes))
            .where(
                OrmContentVersion.catalog_item_id == catalog_item_id,
                OrmContentVersion.is_published.is_(False),
            )
            .order_by(desc(OrmContentVersion.version_number))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_id(self, version_id: str) -> ContentVersion | None:
        stmt = (
            select(OrmContentVersion)
            .options(selectinload(OrmContentVersion.scenes))
            .where(OrmContentVersion.id == version_id)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def save_draft(self, content_version: ContentVersion) -> None:
        stmt = (
            select(OrmContentVersion)
            .options(selectinload(OrmContentVersion.scenes))
            .where(OrmContentVersion.id == content_version.id)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm is None:
            orm = OrmContentVersion(
                id=content_version.id or str(uuid4()),
                catalog_item_id=content_version.catalog_item_id,
                version_number=content_version.version_number,
                revision=content_version.revision,
                is_frozen=content_version.is_frozen,
                is_published=content_version.is_published,
                published_at=content_version.published_at.replace(tzinfo=None)
                if content_version.published_at
                else None,
            )
            self._session.add(orm)
            await self._session.flush()

        orm.revision = content_version.revision
        orm.is_frozen = content_version.is_frozen
        orm.is_published = content_version.is_published
        orm.published_at = content_version.published_at.replace(tzinfo=None) if content_version.published_at else None
        orm.media_asset_id = content_version.media_asset_id
        orm.media_storage_key = content_version.media_storage_key
        orm.media_hls_url = content_version.media_hls_url
        orm.duration_seconds = content_version.duration_seconds
        orm.duration_source = content_version.duration_source
        orm.source_sha256 = content_version.source_sha256
        orm.measured_duration_ms = content_version.measured_duration_ms
        orm.hls_bundle_sha256 = content_version.hls_bundle_sha256

        # Replace scenes
        await self._session.execute(delete(OrmScene).where(OrmScene.content_version_id == orm.id))
        for s in content_version.scenes:
            orm_scene = OrmScene(
                id=s.id or str(uuid4()),
                content_version_id=orm.id,
                scene_index=s.scene_index,
                start_time_seconds=s.start_time_seconds,
                end_time_seconds=s.end_time_seconds,
                title_jp=s.title_jp,
                transcript_jp=s.transcript_jp,
            )
            self._session.add(orm_scene)
        await self._session.flush()

    async def update(self, content_version: ContentVersion) -> None:
        stmt = select(OrmContentVersion).where(OrmContentVersion.id == content_version.id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is not None:
            orm.revision = content_version.revision
            orm.is_frozen = content_version.is_frozen
            orm.is_published = content_version.is_published
            orm.published_at = (
                content_version.published_at.replace(tzinfo=None) if content_version.published_at else None
            )
            orm.media_asset_id = content_version.media_asset_id
            orm.media_storage_key = content_version.media_storage_key
            orm.media_hls_url = content_version.media_hls_url
            orm.duration_seconds = content_version.duration_seconds
            orm.duration_source = content_version.duration_source
            orm.source_sha256 = content_version.source_sha256
            orm.measured_duration_ms = content_version.measured_duration_ms
            orm.hls_bundle_sha256 = content_version.hls_bundle_sha256
            await self._session.flush()

    async def get_max_version_number(self, catalog_item_id: str) -> int:
        stmt = select(func.coalesce(func.max(OrmContentVersion.version_number), 0)).where(
            OrmContentVersion.catalog_item_id == catalog_item_id
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def is_media_pinned(self, asset_id: str) -> bool:
        result = await self._session.execute(
            select(OrmContentVersion.id)
            .where(
                OrmContentVersion.media_asset_id == asset_id,
                (OrmContentVersion.is_frozen.is_(True) | OrmContentVersion.is_published.is_(True)),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
