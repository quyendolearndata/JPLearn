"""SQLAlchemy implementation of CatalogRepository and CatalogQueryPort."""

from __future__ import annotations

from time import time
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.adapters.persistence.models import CatalogItem as OrmCatalogItem
from jplearn_api.adapters.persistence.models import CatalogReview as OrmCatalogReview
from jplearn_api.adapters.persistence.models import ContentVersion as OrmContentVersion
from jplearn_api.adapters.persistence.models import Topic
from jplearn_api.adapters.security.signed_url import sign_hls_url, sign_media_url
from jplearn_api.application.ports.repositories import (
    CatalogQueryPort,
    CatalogRepository,
    UpdateDraftResult,
    UpdateDraftResultStatus,
)
from jplearn_api.application.read_models import CatalogItemPublicDTO
from jplearn_api.domain.catalog import CatalogItem as DomainCatalogItem
from jplearn_api.domain.catalog import CatalogReview, MediaRef
from jplearn_api.settings import Settings


def _to_domain(orm_item: OrmCatalogItem) -> DomainCatalogItem:
    media_refs = [
        MediaRef(
            id=m.id,
            storage_key=m.storage_key,
            playback_url=m.playback_url,
            hls_url=m.hls_url,
            mime=m.mime,
            measured_duration_ms=m.measured_duration_ms,
            source_sha256=m.source_sha256,
            hls_bundle_sha256=m.hls_bundle_sha256,
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
        revision=getattr(orm_item, "revision", 1),
        has_l1_translation=orm_item.has_l1_translation,
        spoken_language=orm_item.spoken_language,
        status=orm_item.status,
        media=media_refs,
        qa_round=orm_item.qa_round,
        reviews=[
            CatalogReview(r.id, r.qa_round, r.decision, r.notes, r.reviewed_by, r.reviewed_at) for r in orm_item.reviews
        ],
    )


class SqlAlchemyCatalogRepository(CatalogRepository):
    """Repository for managing catalog items."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: str) -> DomainCatalogItem | None:
        result = await self._session.execute(
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media), selectinload(OrmCatalogItem.reviews))
            .where(OrmCatalogItem.id == item_id),
        )
        orm_item = result.scalar_one_or_none()
        return _to_domain(orm_item) if orm_item else None

    async def get_by_id_for_update(self, item_id: str) -> DomainCatalogItem | None:
        result = await self._session.execute(
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media), selectinload(OrmCatalogItem.reviews))
            .where(OrmCatalogItem.id == item_id)
            .with_for_update(),
        )
        orm_item = result.scalar_one_or_none()
        return _to_domain(orm_item) if orm_item else None

    async def update_draft_cas(
        self,
        item_id: str,
        expected_revision: int,
        topic_id: str | None = None,
        ci_level: int | None = None,
        duration_seconds: int | None = None,
        media_type: str | None = None,
        visual_support: str | None = None,
        title_internal: str | None = None,
    ) -> UpdateDraftResult:
        values_to_update: dict[str, Any] = {
            "revision": OrmCatalogItem.revision + 1,
        }
        if topic_id is not None:
            values_to_update["topic_id"] = topic_id
        if ci_level is not None:
            values_to_update["ci_level"] = ci_level
        if duration_seconds is not None:
            values_to_update["duration_seconds"] = duration_seconds
        if media_type is not None:
            values_to_update["media_type"] = media_type
        if visual_support is not None:
            values_to_update["visual_support"] = visual_support
        if title_internal is not None:
            values_to_update["title_internal"] = title_internal

        update_stmt = (
            update(OrmCatalogItem)
            .where(
                OrmCatalogItem.id == item_id,
                OrmCatalogItem.status == "draft",
                OrmCatalogItem.revision == expected_revision,
            )
            .values(**values_to_update)
            .returning(OrmCatalogItem)
        )
        result = await self._session.execute(update_stmt)
        orm_item = result.scalar_one_or_none()
        if orm_item is not None:
            await self._session.flush()
            await self._session.refresh(orm_item, ["media", "reviews"])
            return UpdateDraftResult(
                status=UpdateDraftResultStatus.UPDATED,
                item=_to_domain(orm_item),
            )

        # Inspect failure reason
        stmt = select(OrmCatalogItem).where(OrmCatalogItem.id == item_id)
        check_res = await self._session.execute(stmt)
        existing = check_res.scalar_one_or_none()
        if existing is None:
            return UpdateDraftResult(status=UpdateDraftResultStatus.NOT_FOUND)
        if existing.status != "draft":
            return UpdateDraftResult(status=UpdateDraftResultStatus.WRONG_STATUS)
        return UpdateDraftResult(status=UpdateDraftResultStatus.REVISION_CONFLICT)

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
            revision=item.revision,
            has_l1_translation=item.has_l1_translation,
            spoken_language=item.spoken_language,
            status=item.status,
        )
        self._session.add(orm_item)
        await self._session.flush()

    async def update(self, item: DomainCatalogItem) -> None:
        result = await self._session.execute(
            select(OrmCatalogItem).options(selectinload(OrmCatalogItem.reviews)).where(OrmCatalogItem.id == item.id),
        )
        orm_item = result.scalar_one_or_none()
        if orm_item is not None:
            orm_item.topic_id = item.topic_id
            orm_item.ci_level = item.ci_level
            orm_item.duration_seconds = item.duration_seconds
            orm_item.media_type = item.media_type
            orm_item.visual_support = item.visual_support
            orm_item.title_internal = item.title_internal
            orm_item.status = item.status
            orm_item.has_l1_translation = item.has_l1_translation
            orm_item.revision = item.revision
            orm_item.qa_round = item.qa_round
            existing_ids = {r.id for r in orm_item.reviews}
            for review in item.reviews:
                if review.id not in existing_ids:
                    self._session.add(
                        OrmCatalogReview(
                            id=review.id,
                            catalog_item_id=item.id,
                            qa_round=review.qa_round,
                            decision=review.decision,
                            notes=review.notes,
                            reviewed_by=review.reviewed_by,
                            reviewed_at=review.reviewed_at,
                        )
                    )
            await self._session.flush()

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DomainCatalogItem]:
        stmt = (
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media), selectinload(OrmCatalogItem.reviews))
            .order_by(OrmCatalogItem.id.asc())
        )
        if status is not None:
            stmt = stmt.where(OrmCatalogItem.status == status)
        if ci_level is not None:
            stmt = stmt.where(OrmCatalogItem.ci_level == ci_level)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]

    async def topic_exists(self, topic_id: str) -> bool:
        topic = await self._session.get(Topic, topic_id)
        return topic is not None

    async def list_published(
        self,
        ci_level: int | None = None,
        topic_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DomainCatalogItem]:
        stmt = (
            select(OrmCatalogItem)
            .options(selectinload(OrmCatalogItem.media), selectinload(OrmCatalogItem.reviews))
            .where(OrmCatalogItem.status == "published")
            .order_by(OrmCatalogItem.id.asc())
        )
        if ci_level is not None:
            stmt = stmt.where(OrmCatalogItem.ci_level == ci_level)
        if topic_id is not None:
            stmt = stmt.where(OrmCatalogItem.topic_id == topic_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]


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
            .options(selectinload(OrmCatalogItem.media), selectinload(OrmCatalogItem.reviews))
            .where(OrmCatalogItem.status == "published")
            .order_by(OrmCatalogItem.id.asc())
        )
        if ci_level is not None:
            query = query.where(OrmCatalogItem.ci_level == ci_level)
        result = await self._session.execute(query)

        now_sec = int(time())
        items = []
        for item in result.scalars():
            version = (
                await self._session.execute(
                    select(OrmContentVersion)
                    .where(
                        OrmContentVersion.catalog_item_id == item.id,
                        OrmContentVersion.is_published.is_(True),
                    )
                    .order_by(OrmContentVersion.version_number.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            asset = (
                next((a for a in item.media if a.id == version.media_asset_id), None)
                if version and version.media_asset_id
                else (sorted(item.media, key=lambda a: a.id)[0] if item.media else None)
            )
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
