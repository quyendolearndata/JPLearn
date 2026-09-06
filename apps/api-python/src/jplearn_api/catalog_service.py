from datetime import UTC, datetime
from time import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.models import CatalogItem, CatalogReview, MediaAsset, Topic
from jplearn_api.schemas import (CatalogItemPublic, CatalogItemStaff, CatalogItemWrite,
    CatalogItemPatch, CatalogReviewBody, CatalogItemDetail, CatalogReviewPublic)
from jplearn_api.datetime_adapt import to_json_z, to_naive_utc
from jplearn_api.settings import Settings
from jplearn_api.signed_url import sign_hls_url, sign_media_url
from jplearn_api.storage import StoragePort


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


def to_staff(item: CatalogItem, _settings: Settings) -> CatalogItemStaff:
    return CatalogItemStaff(
        id=item.id,
        topic_id=item.topic_id,
        ci_level=item.ci_level,
        duration_seconds=item.duration_seconds,
        media_type=item.media_type,
        visual_support=item.visual_support,
        title_internal=item.title_internal,
        has_l1_translation=item.has_l1_translation,
        status=item.status,
    )



async def _load(session: AsyncSession, item_id: str, *, lock: bool = False) -> CatalogItem:
    query = select(CatalogItem).options(selectinload(CatalogItem.media)).where(CatalogItem.id == item_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(query)
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
    item = await _load(session, item_id, lock=True)
    if item.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft items can be submitted for QA")
    item.qa_round += 1
    item.status = "level_qa"
    await session.commit()
    return to_staff(await _load(session, item_id), settings)


async def publish(
    session: AsyncSession,
    settings: Settings,
    storage: StoragePort,
    item_id: str,
) -> CatalogItemStaff:
    item = await _load(session, item_id, lock=True)
    if item.status != "level_qa":
        raise HTTPException(status_code=400, detail="Only level_qa items can be published")
    assets_result = await session.execute(
        select(MediaAsset).where(MediaAsset.catalog_item_id == item_id)
    )
    assets = assets_result.scalars().all()
    if not assets:
        raise HTTPException(
            status_code=400,
            detail="Cannot publish without media: upload a playback source first (FR-CAT-002)",
        )
    for asset in assets:
        if not await storage.exists(asset.storage_key):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot publish: media file missing from storage for asset {asset.id} (FR-CAT-002)",
            )
    verdict = await session.scalar(select(CatalogReview).where(
        CatalogReview.catalog_item_id == item_id,
        CatalogReview.qa_round == item.qa_round,
        CatalogReview.decision == "approve",
    ))
    if verdict is None:
        raise HTTPException(status_code=400, detail="Current QA round must be approved before publishing")
    item.status = "published"
    await session.commit()
    return to_staff(await _load(session, item_id), settings)


async def unpublish(session: AsyncSession, settings: Settings, item_id: str) -> CatalogItemStaff:
    item = await _load(session, item_id, lock=True)
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


async def list_staff(session: AsyncSession, settings: Settings, status: str | None, limit: int, offset: int):
    query = select(CatalogItem).order_by(CatalogItem.id.asc()).limit(limit).offset(offset)
    if status is not None:
        query = query.where(CatalogItem.status == status)
    return [to_staff(item, settings) for item in (await session.scalars(query)).all()]


async def detail(session: AsyncSession, settings: Settings, item_id: str) -> CatalogItemDetail:
    from jplearn_api.media_service import to_staff as media_to_staff

    # Shared row lock provides a coherent metadata/media/review snapshot while permitting readers.
    await session.execute(select(CatalogItem.id).where(CatalogItem.id == item_id).with_for_update(read=True))
    item = await _load(session, item_id)
    reviews = (await session.scalars(select(CatalogReview).where(
        CatalogReview.catalog_item_id == item_id,
    ).order_by(CatalogReview.qa_round.asc()))).all()
    return CatalogItemDetail(
        **to_staff(item, settings).model_dump(), qa_round=item.qa_round,
        media=[media_to_staff(asset, settings) for asset in item.media],
        reviews=[CatalogReviewPublic(
            id=row.id, qa_round=row.qa_round, decision=row.decision, notes=row.notes,
            reviewed_by=row.reviewed_by, reviewed_at=to_json_z(row.reviewed_at),
        ) for row in reviews],
    )


async def update_draft(session: AsyncSession, settings: Settings, item_id: str, body: CatalogItemPatch):
    item = await _load(session, item_id, lock=True)
    if item.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft items can be edited")
    values = body.model_dump(exclude_unset=True)
    if "topic_id" in values and await session.get(Topic, values["topic_id"]) is None:
        raise HTTPException(status_code=400, detail="Unknown topic_id")
    for name, value in values.items():
        setattr(item, name, value)
    result = to_staff(item, settings)
    await session.commit()
    return result


async def review(session: AsyncSession, settings: Settings, item_id: str, body: CatalogReviewBody, reviewer_id: str):
    item = await _load(session, item_id, lock=True)
    if item.status != "level_qa":
        raise HTTPException(status_code=400, detail="Only level_qa items can be reviewed")
    previous = await session.scalar(select(CatalogReview.id).where(
        CatalogReview.catalog_item_id == item_id, CatalogReview.qa_round == item.qa_round,
    ))
    if previous is not None:
        raise HTTPException(status_code=400, detail="This QA round has already been reviewed")
    session.add(CatalogReview(
        id=str(uuid4()), catalog_item_id=item.id, qa_round=item.qa_round,
        decision=body.decision, notes=body.notes, reviewed_by=reviewer_id,
        reviewed_at=to_naive_utc(datetime.now(UTC)),
    ))
    if body.decision == "reject":
        item.status = "draft"
    result = to_staff(item, settings)
    await session.commit()
    return result
