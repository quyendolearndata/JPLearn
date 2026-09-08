"""SQLAlchemy implementation of FlagsRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import FeatureFlag
from jplearn_api.application.ports.repositories import FlagsRepository

FLAG_KEYS = (
    "speaking_enabled",
    "l1_subtitles_enabled",
    "grammar_enabled",
    "flashcards_enabled",
)


class SqlAlchemyFlagsRepository(FlagsRepository):
    """PostgreSQL/SQLAlchemy implementation of FlagsRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_defaults(self) -> None:
        for key in FLAG_KEYS:
            await self._session.execute(
                insert(FeatureFlag).values(key=key, value=False).on_conflict_do_nothing(index_elements=["key"]),
            )

    async def get_flags(self) -> dict[str, bool]:
        await self.ensure_defaults()
        result = await self._session.execute(
            select(FeatureFlag).where(FeatureFlag.key.in_(FLAG_KEYS)),
        )
        values = {row.key: row.value for row in result.scalars()}
        return {key: bool(values.get(key, False)) for key in FLAG_KEYS}

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        for key in FLAG_KEYS:
            if key in flags:
                stmt = insert(FeatureFlag).values(key=key, value=flags[key])
                stmt = stmt.on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": flags[key]},
                )
                await self._session.execute(stmt)
        return await self.get_flags()
