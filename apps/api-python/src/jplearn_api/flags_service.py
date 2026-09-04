from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.models import FeatureFlag
from jplearn_api.schemas import Flags

FLAG_KEYS = (
    "speaking_enabled",
    "l1_subtitles_enabled",
    "grammar_enabled",
    "flashcards_enabled",
)


async def ensure_defaults(session: AsyncSession) -> None:
    for key in FLAG_KEYS:
        await session.execute(
            insert(FeatureFlag).values(key=key, value=False).on_conflict_do_nothing(index_elements=["key"]),
        )
    await session.commit()


async def get_flags(session: AsyncSession) -> Flags:
    await ensure_defaults(session)
    result = await session.execute(select(FeatureFlag).where(FeatureFlag.key.in_(FLAG_KEYS)))
    values = {row.key: row.value for row in result.scalars()}
    return Flags.model_validate({key: bool(values.get(key, False)) for key in FLAG_KEYS})


async def update_flags(session: AsyncSession, flags: Flags) -> Flags:
    payload = flags.model_dump()
    for key in FLAG_KEYS:
        stmt = insert(FeatureFlag).values(key=key, value=payload[key])
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": payload[key]})
        await session.execute(stmt)
    await session.commit()
    return await get_flags(session)
