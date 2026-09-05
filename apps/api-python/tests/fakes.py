"""Test fakes for Clean Architecture unit testing (Zero external I/O).

Provides transactional state isolation, deep-copying, and commit/rollback guarantees.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import contextvars
import copy
from types import TracebackType
from typing import Any

from jplearn_api.application.ports.repositories import (
    CatalogRepository,
    FlagsRepository,
    LearningRepository,
    MediaRepository,
    UserRepository,
)
from jplearn_api.application.ports.security import MediaUrlSigner
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork

_active_fake_uow: contextvars.ContextVar[FakeUnitOfWork | None] = contextvars.ContextVar(
    "_active_fake_uow", default=None
)



class FakeFlagsRepository(FlagsRepository):
    """In-memory fake implementation of FlagsRepository with transaction isolation."""

    def __init__(self, initial_flags: dict[str, bool] | None = None) -> None:
        defaults = {
            "speaking_enabled": False,
            "l1_subtitles_enabled": False,
            "grammar_enabled": False,
            "flashcards_enabled": False,
        }
        if initial_flags:
            defaults.update(initial_flags)
        self._committed_flags: dict[str, bool] = dict(defaults)
        self.flags: dict[str, bool] = dict(defaults)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.flags = copy.deepcopy(self._committed_flags)

    def commit_transaction(self) -> None:
        self._committed_flags = copy.deepcopy(self.flags)

    def rollback_transaction(self) -> None:
        self.flags = copy.deepcopy(self._committed_flags)

    async def ensure_defaults(self) -> None:
        pass

    async def get_flags(self) -> dict[str, bool]:
        self._auto_register()
        return dict(self.flags)

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        self._auto_register()
        self.flags.update(flags)
        if _active_fake_uow.get() is None:
            self._committed_flags.update(flags)
        return dict(self.flags)


class FakePasswordHasher:
    """In-memory password hasher fake."""

    async def hash_password(self, password: str) -> str:
        return f"hashed_{password}"

    async def verify_password(self, password_hash: str, candidate: str) -> bool:
        return password_hash == f"hashed_{candidate}"


class FakeTokenService:
    """In-memory token service fake."""

    def sign_access_token(
        self,
        user_id: str,
        email: str,
        token_version: int,
        secret: str,
    ) -> str:
        return f"fake_jwt_{user_id}_{token_version}"

    def decode_access_token(self, token: str, secret: str) -> dict[str, object]:
        parts = token.split("_")
        return {"sub": parts[2], "ver": int(parts[3])}


class FakeUserRepository(UserRepository):
    """In-memory fake implementation of UserRepository with transaction isolation."""

    def __init__(self) -> None:
        self._committed_users: dict[str, Any] = {}
        self._committed_email_index: dict[str, str] = {}
        self._committed_roles: dict[str, list[str]] = {}
        self._committed_progress: dict[str, Any] = {}

        self.users: dict[str, Any] = {}
        self.email_index: dict[str, str] = {}
        self.roles: dict[str, list[str]] = {}
        self.progress: dict[str, Any] = {}

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.users = copy.deepcopy(self._committed_users)
        self.email_index = copy.deepcopy(self._committed_email_index)
        self.roles = copy.deepcopy(self._committed_roles)
        self.progress = copy.deepcopy(self._committed_progress)

    def commit_transaction(self) -> None:
        self._committed_users = copy.deepcopy(self.users)
        self._committed_email_index = copy.deepcopy(self.email_index)
        self._committed_roles = copy.deepcopy(self.roles)
        self._committed_progress = copy.deepcopy(self.progress)

    def rollback_transaction(self) -> None:
        self.users = copy.deepcopy(self._committed_users)
        self.email_index = copy.deepcopy(self._committed_email_index)
        self.roles = copy.deepcopy(self._committed_roles)
        self.progress = copy.deepcopy(self._committed_progress)

    async def get_by_id(self, user_id: str) -> Any:
        self._auto_register()
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> Any:
        self._auto_register()
        uid = self.email_index.get(email.strip().lower())
        return self.users.get(uid) if uid else None

    async def add(self, user: Any) -> None:
        self._auto_register()
        from jplearn_api.domain.errors import DuplicateEmailError

        normalized = user.email.strip().lower()
        if normalized in self.email_index:
            raise DuplicateEmailError("Email already registered")
        self.users[user.id] = copy.deepcopy(user)
        self.email_index[normalized] = user.id
        self.roles[user.id] = list(user.roles)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def update(self, user: Any) -> None:
        self._auto_register()
        if user.id in self.users:
            self.users[user.id] = copy.deepcopy(user)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def add_role(self, user_id: str, role: str) -> None:
        self._auto_register()
        if user_id in self.roles:
            self.roles[user_id].append(role)
        else:
            self.roles[user_id] = [role]
        if user_id in self.users:
            self.users[user_id].roles = list(self.roles[user_id])
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def add_initial_progress(self, user_id: str, now: Any) -> None:
        self._auto_register()
        self.progress[user_id] = {"now": now}
        if _active_fake_uow.get() is None:
            self.commit_transaction()


class FakeStoragePort(StoragePort):
    """In-memory fake storage port."""

    def __init__(self, existing_keys: set[str] | None = None) -> None:
        self.keys = set(existing_keys or ())
        self.files: dict[str, bytes] = {}

    async def stage_stream(self, temp_key: str, stream: AsyncIterator[bytes], *, max_bytes: int = 500 * 1024 * 1024) -> int:
        total = 0
        chunks = []
        async for chunk in stream:
            total += len(chunk)
            chunks.append(chunk)
        self.files[temp_key] = b"".join(chunks)
        self.keys.add(temp_key)
        return total

    async def promote(self, temp_key: str, final_key: str) -> None:
        if temp_key in self.files:
            self.files[final_key] = self.files.pop(temp_key)
        self.keys.discard(temp_key)
        self.keys.add(final_key)

    async def delete(self, key: str) -> bool:
        self.files.pop(key, None)
        if key in self.keys:
            self.keys.discard(key)
            return True
        return False

    async def exists(self, key: str) -> bool:
        return key in self.keys

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        data = self.files.get(key, b"")
        async def _iter():
            yield data
        return _iter()

    async def open_read_range(self, key: str, start: int, length: int) -> AsyncIterator[bytes]:
        data = self.files.get(key, b"")[start : start + length]
        async def _iter():
            yield data
        return _iter()

    async def get_metadata(self, key: str) -> Any:
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class _Meta:
            size: int
            mtime: float
        data = self.files.get(key, b"")
        return _Meta(size=len(data), mtime=1700000000.0)

    async def list_keys(self) -> list[str]:
        return list(self.keys)

    async def check_ready(self) -> tuple[bool, str]:
        return True, "ok"

    async def check_readiness(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class FakeCatalogRepository(CatalogRepository):
    """In-memory fake implementation of CatalogRepository with transaction isolation."""

    def __init__(self) -> None:
        self._committed_items: dict[str, Any] = {}
        self.items: dict[str, Any] = {}
        self.topics: set[str] = {"topic_valid"}

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.items = copy.deepcopy(self._committed_items)

    def commit_transaction(self) -> None:
        self._committed_items = copy.deepcopy(self.items)

    def rollback_transaction(self) -> None:
        self.items = copy.deepcopy(self._committed_items)

    async def get_by_id(self, item_id: str) -> Any:
        self._auto_register()
        item = self.items.get(item_id)
        return copy.deepcopy(item) if item else None

    async def add(self, item: Any) -> None:
        self._auto_register()
        self.items[item.id] = copy.deepcopy(item)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def update(self, item: Any) -> None:
        self._auto_register()
        self.items[item.id] = copy.deepcopy(item)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def topic_exists(self, topic_id: str) -> bool:
        return topic_id in self.topics


class FakeLearningRepository(LearningRepository):
    """In-memory fake implementation of LearningRepository with transaction isolation."""

    def __init__(self, initial_progress: dict[str, Any] | None = None) -> None:
        self._committed_sessions: dict[str, Any] = {}
        self._committed_progress: dict[str, Any] = copy.deepcopy(initial_progress or {})
        self._committed_devices: dict[tuple[str, str], Any] = {}
        self._committed_events: list[dict[str, Any]] = []

        self.sessions: dict[str, Any] = {}
        self.progress: dict[str, Any] = copy.deepcopy(initial_progress or {})
        self.devices: dict[tuple[str, str], Any] = {}
        self.events: list[dict[str, Any]] = []

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.sessions = copy.deepcopy(self._committed_sessions)
        self.progress = copy.deepcopy(self._committed_progress)
        self.devices = copy.deepcopy(self._committed_devices)
        self.events = copy.deepcopy(self._committed_events)

    def commit_transaction(self) -> None:
        self._committed_sessions = copy.deepcopy(self.sessions)
        self._committed_progress = copy.deepcopy(self.progress)
        self._committed_devices = copy.deepcopy(self.devices)
        self._committed_events = copy.deepcopy(self.events)

    def rollback_transaction(self) -> None:
        self.sessions = copy.deepcopy(self._committed_sessions)
        self.progress = copy.deepcopy(self._committed_progress)
        self.devices = copy.deepcopy(self._committed_devices)
        self.events = copy.deepcopy(self._committed_events)

    async def create_session(self, session: Any) -> None:
        self._auto_register()
        self.sessions[session.id] = copy.deepcopy(session)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def lock_and_get_session(self, session_id: str) -> Any:
        self._auto_register()
        return self.sessions.get(session_id)

    async def update_session(self, session: Any) -> None:
        self._auto_register()
        self.sessions[session.id] = copy.deepcopy(session)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def upsert_device(self, user_id: str, device_class: str, last_seen_at: Any) -> None:
        self._auto_register()
        self.devices[(user_id, device_class)] = last_seen_at
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def get_progress(self, user_id: str) -> Any:
        self._auto_register()
        return self.progress.get(user_id)

    async def lock_and_get_progress(self, user_id: str) -> Any:
        self._auto_register()
        return self.progress.get(user_id)

    async def update_progress(self, progress: Any) -> None:
        self._auto_register()
        self.progress[progress.user_id] = copy.deepcopy(progress)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def record_event(
        self,
        user_id: str,
        session_id: str | None,
        event_type: str,
        payload: dict,
        created_at: Any,
    ) -> None:
        self._auto_register()
        self.events.append({
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "payload": dict(payload),
            "created_at": created_at,
        })
        if _active_fake_uow.get() is None:
            self.commit_transaction()


class FakeMediaRepository(MediaRepository):
    """In-memory fake implementation of MediaRepository with transaction isolation."""

    def __init__(
        self,
        initial_assets: dict[str, Any] | None = None,
        existing_items: set[str] | None = None,
    ) -> None:
        self._committed_assets: dict[str, Any] = copy.deepcopy(initial_assets or {})
        self.assets: dict[str, Any] = copy.deepcopy(initial_assets or {})
        self.catalog_items: set[str] = set(existing_items or [])

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.assets = copy.deepcopy(self._committed_assets)

    def commit_transaction(self) -> None:
        self._committed_assets = copy.deepcopy(self.assets)

    def rollback_transaction(self) -> None:
        self.assets = copy.deepcopy(self._committed_assets)

    async def get_by_id(self, asset_id: str) -> Any:
        self._auto_register()
        asset = self.assets.get(asset_id)
        return copy.deepcopy(asset) if asset else None

    async def add(self, asset: Any) -> None:
        self._auto_register()
        self.assets[asset.id] = copy.deepcopy(asset)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def update(self, asset: Any) -> None:
        self._auto_register()
        self.assets[asset.id] = copy.deepcopy(asset)
        if _active_fake_uow.get() is None:
            self.commit_transaction()

    async def catalog_item_exists(self, catalog_item_id: str) -> bool:
        return catalog_item_id in self.catalog_items

    async def list_all_storage_keys(self) -> set[str]:
        self._auto_register()
        return {
            getattr(a, "storage_key", "")
            for a in self.assets.values()
            if getattr(a, "storage_key", None)
        }

    async def storage_key_exists(self, storage_key: str) -> bool:
        self._auto_register()
        return any(getattr(a, "storage_key", None) == storage_key for a in self.assets.values())


class FakeUnitOfWork(AsyncUnitOfWork):
    """In-memory Unit of Work recording commit/rollback actions with transactional state isolation."""

    def __init__(
        self,
        *participants: Any,
        users: UserRepository | None = None,
        catalog: CatalogRepository | None = None,
        media: MediaRepository | None = None,
        learning: LearningRepository | None = None,
        flags: FlagsRepository | None = None,
    ) -> None:
        self.participants: list[Any] = list(participants)
        self.committed = False
        self.rolled_back = False
        self._reset_token: contextvars.Token | None = None

        resolved_users = users
        resolved_catalog = catalog
        resolved_media = media
        resolved_learning = learning
        resolved_flags = flags

        for p in self.participants:
            if isinstance(p, FakeUserRepository) and resolved_users is None:
                resolved_users = p
            elif isinstance(p, FakeCatalogRepository) and resolved_catalog is None:
                resolved_catalog = p
            elif isinstance(p, FakeMediaRepository) and resolved_media is None:
                resolved_media = p
            elif isinstance(p, FakeLearningRepository) and resolved_learning is None:
                resolved_learning = p
            elif isinstance(p, FakeFlagsRepository) and resolved_flags is None:
                resolved_flags = p

        self.users = resolved_users or FakeUserRepository()
        self.catalog = resolved_catalog or FakeCatalogRepository()
        self.media = resolved_media or FakeMediaRepository()
        self.learning = resolved_learning or FakeLearningRepository()
        self.flags = resolved_flags or FakeFlagsRepository()

        for repo in (self.users, self.catalog, self.media, self.learning, self.flags):
            self.register(repo)

        for p in self.participants:
            if hasattr(p, "bind_uow"):
                p.bind_uow(self)

    def register(self, participant: Any) -> None:
        if participant not in self.participants:
            self.participants.append(participant)
            if hasattr(participant, "bind_uow"):
                participant.bind_uow(self)

    async def __aenter__(self) -> FakeUnitOfWork:
        self.committed = False
        self.rolled_back = False
        self._reset_token = _active_fake_uow.set(self)
        for p in self.participants:
            if hasattr(p, "begin_transaction"):
                p.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None or not self.committed:
                await self.rollback()
        finally:
            if self._reset_token is not None:
                _active_fake_uow.reset(self._reset_token)
                self._reset_token = None

    async def commit(self) -> None:
        self.committed = True
        for p in self.participants:
            if hasattr(p, "commit_transaction"):
                p.commit_transaction()

    async def rollback(self) -> None:
        self.rolled_back = True
        for p in self.participants:
            if hasattr(p, "rollback_transaction"):
                p.rollback_transaction()


class FakeMediaUrlSigner(MediaUrlSigner):
    """In-memory fake MediaUrlSigner generating deterministic URLs without secret credentials."""

    def __init__(self, base_url: str = "http://localhost:3001") -> None:
        self._base_url = base_url.rstrip("/")

    def sign_playback_url(self, asset_id: str) -> str:
        return f"{self._base_url}/media/{asset_id}?exp=9999999999&sig=fakesig"

    def sign_hls_url(self, asset_id: str) -> str:
        return f"{self._base_url}/media/{asset_id}/hls/index.m3u8?exp=9999999999&sig=fakesig"

    def playback_url(self, asset_id: str) -> str:
        return f"{self._base_url}/media/{asset_id}"

    def manifest_url(self, asset_id: str) -> str:
        return f"{self._base_url}/media/{asset_id}/hls/index.m3u8"

    def verify_media_sig(self, asset_id: str, exp: int, sig: str) -> bool:
        return sig == "fakesig"

