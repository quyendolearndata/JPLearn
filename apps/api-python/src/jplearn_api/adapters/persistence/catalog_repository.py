"""SQLAlchemy implementation of CatalogRepository and CatalogQueryPort."""

from __future__ import annotations

from time import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.application.ports.repositories import CatalogQueryPort, CatalogRepository
from jplearn_api.application.read_models import CatalogItemPublicDTO
from jplearn_api.domain.catalog import CatalogItem as DomainCatalogItem, MediaRef
from jplearn_api.adapters.persistence.models import CatalogItem as OrmCatalogItem, Topic
from jplearn_api.settings import Settings
from jplearn_api.adapters.security.signed_url import sign_hls_url, sign_media_url


def _to_domain(orm_item: OrmCatalogItem) -> DomainCatalogItem:
    media_refs = [
        MediaRef(
            id=m.id,
            storage_key=m.storage_key,
            playback_url=m.playback_url,
            hls_url=m.hls_url,
            mime=m.mime,
        )
        for m in orm_item.media
    ]
    return DomainCatalogItem(
        id=orm_item.id,
        topic_id=orm_item.topic_id,
        ci_level=orm_item.ci_level,
        duration_seconds=orm_item.duration_seconds,
        media_type=orm_item.media_type,
        visual_support=orm_item.visual_support,
        title_internal=orm_item.title_internal,
        created_by=orm_item.created_by,
        has_l1_translation=orm_item.has_l1_translation,
        spoken_language=orm_item.spoken_language,
        status=orm_item.status,
        media=media_refs,
    )


class SqlAlchemyCatalogRepository(CatalogRepository):
    """PostgreSQL/SQLAlchemy implementation of CatalogRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: str) -> DomainCatalogItem | None:
        result = await self._session.execute(
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media))
            .where(OrmCatalogItem.id == item_id),
        )
        orm_item = result.scalar_one_or_none()
        return _to_domain(orm_item) if orm_item else None

    async def add(self, item: DomainCatalogItem) -> None:
        orm_item = OrmCatalogItem(
            id=item.id,
            topic_id=item.topic_id,
            ci_level=item.ci_level,
            duration_seconds=item.duration_seconds,
            media_type=item.media_type,
            visual_support=item.visual_support,
            title_internal=item.title_internal,
            created_by=item.created_by,
            has_l1_translation=item.has_l1_translation,
            spoken_language=item.spoken_language,
            status=item.status,
        )
        self._session.add(orm_item)
        await self._session.flush()

    async def update(self, item: DomainCatalogItem) -> None:
        result = await self._session.execute(
            select(OrmCatalogItem).where(OrmCatalogItem.id == item.id),
        )
        orm_item = result.scalar_one_or_none()
        if orm_item is not None:
            orm_item.status = item.status
            orm_item.has_l1_translation = item.has_l1_translation
            await self._session.flush()

    async def topic_exists(self, topic_id: str) -> bool:
        topic = await self._session.get(Topic, topic_id)
        return topic is not None


class SqlAlchemyCatalogQueryAdapter(CatalogQueryPort):
    """Query adapter for reading published catalog items."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def _secret(self) -> str:
        return self._settings.media_signing_secret or self._settings.jwt_secret

    def _base_url(self) -> str:
        if not self._settings.api_public_url:
            raise RuntimeError("API_PUBLIC_URL must be set")
        return self._settings.api_public_url.rstrip("/")

    async def list_published(self, ci_level: int | None) -> list[CatalogItemPublicDTO]:
        query = (
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media))
            .where(OrmCatalogItem.status == "published")
            .order_by(OrmCatalogItem.id.asc())
        )
        if ci_level is not None:
            query = query.where(OrmCatalogItem.ci_level == ci_level)
        result = await self._session.execute(query)

        now_sec = int(time())
        items = []
        for item in result.scalars():
            asset = item.media[0] if item.media else None
            playback_url = (
                sign_media_url(
                    asset_id=asset.id,
                    base_url=self._base_url(),
                    secret=self._secret(),
                    now_sec=now_sec,
                )
                if asset
                else None
            )
            hls_url = (
                sign_hls_url(
                    asset_id=asset.id,
                    base_url=self._base_url(),
                    secret=self._secret(),
                    now_sec=now_sec,
                )
                if asset and asset.hls_url
                else None
            )
            items.append(
                CatalogItemPublicDTO(
                    id=item.id,
                    ci_level=item.ci_level,
                    duration_seconds=item.duration_seconds,
                    media_type=item.media_type,
                    topic_id=item.topic_id,
                    visual_support=item.visual_support,
                    playback_url=playback_url,
                    hls_url=hls_url,
                )
            )
        return items
