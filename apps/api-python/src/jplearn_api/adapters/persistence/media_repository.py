"""SQLAlchemy implementation of MediaRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.ports.repositories import MediaRepository
from jplearn_api.domain.errors import DeterministicAbortError
from jplearn_api.domain.media import MediaAsset as DomainMediaAsset
from jplearn_api.adapters.persistence.models import CatalogItem as OrmCatalogItem, MediaAsset as OrmMediaAsset


def _to_domain(orm_asset: OrmMediaAsset) -> DomainMediaAsset:
    return DomainMediaAsset(
        id=orm_asset.id,
        catalog_item_id=orm_asset.catalog_item_id,
        storage_key=orm_asset.storage_key,
        playback_url=orm_asset.playback_url,
        hls_url=orm_asset.hls_url,
        mime=orm_asset.mime,
        measured_duration_ms=orm_asset.measured_duration_ms,
        source_sha256=orm_asset.source_sha256,
        hls_bundle_sha256=orm_asset.hls_bundle_sha256,
    )


class SqlAlchemyMediaRepository(MediaRepository):
    """PostgreSQL/SQLAlchemy implementation of MediaRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, asset_id: str) -> DomainMediaAsset | None:
        orm_asset = await self._session.get(OrmMediaAsset, asset_id)
        if orm_asset is None:
            return None
        return _to_domain(orm_asset)

    async def add(self, asset: DomainMediaAsset) -> None:
        orm_asset = OrmMediaAsset(
            id=asset.id,
            catalog_item_id=asset.catalog_item_id,
            storage_key=asset.storage_key,
            playback_url=asset.playback_url,
            hls_url=asset.hls_url,
            mime=asset.mime,
            measured_duration_ms=asset.measured_duration_ms,
            source_sha256=asset.source_sha256,
            hls_bundle_sha256=asset.hls_bundle_sha256,
        )
        self._session.add(orm_asset)
        if hasattr(self._session, "flush"):
            try:
                await self._session.flush()
            except IntegrityError as exc:
                raise DeterministicAbortError(str(exc)) from exc

    async def update(self, asset: DomainMediaAsset) -> None:
        orm_asset = await self._session.get(OrmMediaAsset, asset.id)
        if orm_asset is not None:
            orm_asset.hls_url = asset.hls_url
            orm_asset.playback_url = asset.playback_url
            orm_asset.hls_bundle_sha256 = asset.hls_bundle_sha256

    async def catalog_item_exists(self, catalog_item_id: str) -> bool:
        item = await self._session.get(OrmCatalogItem, catalog_item_id)
        return item is not None

    async def get_catalog_item_status(self, catalog_item_id: str, *, for_update: bool = False) -> str | None:
        item = await self._session.get(OrmCatalogItem, catalog_item_id, with_for_update=for_update, populate_existing=for_update)
        if item is None:
            return None
        return getattr(item, "status", "draft")

    async def list_all_storage_keys(self) -> set[str]:
        result = await self._session.execute(select(OrmMediaAsset.storage_key))
        return set(result.scalars().all())

    async def storage_key_exists(self, storage_key: str) -> bool:
        result = await self._session.execute(
            select(OrmMediaAsset.id).where(OrmMediaAsset.storage_key == storage_key)
        )
        return result.scalar_one_or_none() is not None
