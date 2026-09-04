from time import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.models import CatalogItem, MediaAsset, Topic
from jplearn_api.schemas import CatalogItemPublic, CatalogItemStaff, CatalogItemWrite, MediaAssetStaff
from jplearn_api.settings import Settings
from jplearn_api.signed_url import sign_hls_url, sign_media_url


def _secret(settings: Settings) -> str:
    return settings.media_signing_secret or settings.jwt_secret


def _base_url(settings: Settings) -> str:
    if not settings.api_public_url:
        raise RuntimeError("API_PUBLIC_URL must be set")
    return settings.api_public_url.rstrip("/")


def _signed_playback(asset_id: str, settings: Settings) -> str:
    return sign_media_url(
        asset_id=asset_id,
        base_url=_base_url(settings),
        secret=_secret(settings),
        now_sec=int(time()),
    )


def _signed_hls(asset_id: str, settings: Settings) -> str:
    return sign_hls_url(
        asset_id=asset_id,
        base_url=_base_url(settings),
        secret=_secret(settings),
        now_sec=int(time()),
    )


def to_public(item: CatalogItem, settings: Settings) -> CatalogItemPublic:
    asset = item.media[0] if item.media else None
    return CatalogItemPublic(
        id=item.id,
        ci_level=item.ci_level,
        duration_seconds=item.duration_seconds,
        media_type=item.media_type,
        topic_id=item.topic_id,
        visual_support=item.visual_support,
        playback_url=_signed_playback(asset.id, settings) if asset else None,
        hls_url=_signed_hls(asset.id, settings) if asset and asset.hls_url else None,
    )


def to_staff(item: CatalogItem, settings: Settings) -> CatalogItemStaff:
    return CatalogItemStaff(
        id=item.id,
        topic_id=item.topic_id,
        ci_level=item.ci_level,
        duration_seconds=item.duration_seconds,
        media_type=item.media_type,
        visual_support=item.visual_support,
        title_internal=item.title_internal,
        has_l1_translation=item.has_l1_translation,
        spoken_language=item.spoken_language,
        status=item.status,
        created_by=item.created_by,
        media=[
            MediaAssetStaff(
                id=asset.id,
                catalog_item_id=asset.catalog_item_id,
                storage_key=asset.storage_key,
                playback_url=_signed_playback(asset.id, settings),
                hls_url=_signed_hls(asset.id, settings) if asset.hls_url else None,
                mime=asset.mime,
            )
            for asset in item.media
        ],
    )


async def _load(session: AsyncSession, item_id: str) -> CatalogItem:
    result = await session.execute(
        select(CatalogItem).options(selectinload(CatalogItem.media)).where(CatalogItem.id == item_id),
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return item


async def create(session: AsyncSession, settings: Settings, body: CatalogItemWrite, created_by: str) -> CatalogItemStaff:
    topic = await session.get(Topic, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=400, detail="Unknown topic_id")
    item = CatalogItem(
        id=str(uuid4()),
        topic_id=body.topic_id,
        ci_level=body.ci_level,
        duration_seconds=body.duration_seconds,
        media_type=body.media_type,
        visual_support=body.visual_support,
        title_internal=body.title_internal,
        created_by=created_by,
        has_l1_translation=False,
        spoken_language="ja",
        status="draft",
    )
    session.add(item)
    await session.commit()
    return to_staff(await _load(session, item.id), settings)


async def submit_qa(session: AsyncSession, settings: Settings, item_id: str) -> CatalogItemStaff:
    item = await _load(session, item_id)
    if item.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft items can be submitted for QA")
    item.status = "level_qa"
    await session.commit()
    return to_staff(await _load(session, item_id), settings)


async def publish(session: AsyncSession, settings: Settings, item_id: str) -> CatalogItemStaff:
    item = await _load(session, item_id)
    if item.status != "level_qa":
        raise HTTPException(status_code=400, detail="Only level_qa items can be published")
    count = await session.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.catalog_item_id == item_id),
    )
    if not count:
        raise HTTPException(
            status_code=400,
            detail="Cannot publish without media: upload a playback source first (FR-CAT-002)",
        )
    item.status = "published"
    await session.commit()
    return to_staff(await _load(session, item_id), settings)


async def unpublish(session: AsyncSession, settings: Settings, item_id: str) -> CatalogItemStaff:
    item = await _load(session, item_id)
    if item.status != "published":
        raise HTTPException(status_code=400, detail="Only published items can be unpublished")
    item.status = "draft"
    await session.commit()
    return to_staff(await _load(session, item_id), settings)


async def list_published(
    session: AsyncSession,
    settings: Settings,
    ci_level: int | None,
) -> list[CatalogItemPublic]:
    query = (
        select(CatalogItem)
        .options(selectinload(CatalogItem.media))
        .where(CatalogItem.status == "published")
        .order_by(CatalogItem.id.asc())
    )
    if ci_level is not None:
        query = query.where(CatalogItem.ci_level == ci_level)
    result = await session.execute(query)
    return [to_public(item, settings) for item in result.scalars()]
