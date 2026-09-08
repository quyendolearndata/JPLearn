import asyncio
import pytest

from fakes import FakeStoragePort
from jplearn_api.application.handlers.media import UploadTransactionCoordinator
from jplearn_api.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork, drain_quarantined_scopes


@pytest.mark.asyncio
async def test_timeout_quarantines_session_until_cancel_resistant_rollback_ends():
    release = asyncio.Event()
    closed = asyncio.Event()
    class Session:
        active = False
        async def rollback(self):
            self.active = True
            try:
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
            finally:
                self.active = False
        async def close(self):
            assert not self.active, "close must never overlap rollback"
            closed.set()
    session = Session()
    uow = SqlAlchemyUnitOfWork(lambda: session)
    await uow.__aenter__()
    coordinator = UploadTransactionCoordinator(uow, FakeStoragePort(), "a", "c", "a.bin", .01)
    await coordinator.settle_rollback_and_cleanup("fault")
    assert not uow.rolled_back
    assert not coordinator.cleanup_task.done()
    await uow.__aexit__(RuntimeError, RuntimeError("original"), None)
    assert not closed.is_set()
    with pytest.raises(RuntimeError, match="admission suspended"):
        await SqlAlchemyUnitOfWork(lambda: Session()).__aenter__()
    with pytest.raises(RuntimeError, match="Pending UoW cleanup"):
        await drain_quarantined_scopes(.01)
    release.set()
    await drain_quarantined_scopes(1)
    assert closed.is_set()
    assert uow.rolled_back


@pytest.mark.asyncio
async def test_rollback_failure_never_sets_confirmed_flag_and_close_is_observed():
    class Session:
        closed = False
        async def rollback(self): raise RuntimeError("rollback unavailable")
        async def close(self): self.closed = True
    session = Session()
    uow = SqlAlchemyUnitOfWork(lambda: session)
    await uow.__aenter__()
    storage = FakeStoragePort({"a.bin"})
    coordinator = UploadTransactionCoordinator(uow, storage, "a", "c", "a.bin", 1)
    await coordinator.settle_rollback_and_cleanup("fault")
    await uow.__aexit__(RuntimeError, RuntimeError("original"), None)
    await drain_quarantined_scopes(1)
    assert not uow.rolled_back
    assert "a.bin" in storage.keys
    assert session.closed


@pytest.mark.asyncio
async def test_postgres_quarantined_rollback_keeps_connection_until_settled(live_database_url):
    from sqlalchemy import text
    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from conftest import _settings
    engine, factory = create_engine_and_sessions(_settings(live_database_url))
    release = asyncio.Event()
    uow = SqlAlchemyUnitOfWork(factory)
    try:
        await uow.__aenter__()
        await uow.session.execute(text("SELECT 1"))
        original = uow.rollback
        async def delayed_rollback():
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            await original()
        uow.rollback = delayed_rollback
        coordinator = UploadTransactionCoordinator(uow, FakeStoragePort(), "a", "c", "a.bin", .01)
        await coordinator.settle_rollback_and_cleanup("postgres_fault")
        await uow.__aexit__(RuntimeError, RuntimeError("original"), None)
        assert engine.pool.checkedout() == 1
        assert not uow.rolled_back
        release.set()
        await drain_quarantined_scopes(1)
        assert uow.rolled_back
        assert engine.pool.checkedout() == 0
    finally:
        release.set()
        await drain_quarantined_scopes(1)
        await engine.dispose()


@pytest.mark.asyncio
async def test_close_failure_does_not_replace_original_error(caplog):
    class Session:
        async def rollback(self): pass
        async def close(self): raise RuntimeError("close failed")
    uow = SqlAlchemyUnitOfWork(lambda: Session())
    with pytest.raises(ValueError, match="original"):
        async with uow:
            coordinator = UploadTransactionCoordinator(uow, FakeStoragePort(), "a", "c", "a.bin", 1)
            await coordinator.settle_rollback_and_cleanup("fault")
            raise ValueError("original")
    assert "uow_deferred_close_failed" in caplog.text
