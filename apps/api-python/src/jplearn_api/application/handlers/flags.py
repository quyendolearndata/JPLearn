"""Feature flags use case handlers (Pure Python)."""

from __future__ import annotations

from jplearn_api.application.commands import UpdateFlagsCommand
from jplearn_api.application.ports.repositories import FlagsRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork


async def handle_get_flags(repo: FlagsRepository) -> dict[str, bool]:
    """Read feature flags after ensuring defaults."""
    return await repo.get_flags()


async def handle_update_flags(
    cmd: UpdateFlagsCommand,
    uow: AsyncUnitOfWork,
    repo: FlagsRepository,
) -> dict[str, bool]:
    """Atomically update feature flags inside a Unit of Work."""
    async with uow:
        updated = await repo.update_flags(cmd.flags)
        await uow.commit()
    return updated
