"""Test fakes for Clean Architecture unit testing (Zero external I/O)."""

from __future__ import annotations

from types import TracebackType

from jplearn_api.application.ports.repositories import FlagsRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork


class FakeUnitOfWork(AsyncUnitOfWork):
    """In-memory Unit of Work recording commit/rollback actions."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeFlagsRepository(FlagsRepository):
    """In-memory fake implementation of FlagsRepository."""

    def __init__(self, initial_flags: dict[str, bool] | None = None) -> None:
        self.flags: dict[str, bool] = {
            "speaking_enabled": False,
            "l1_subtitles_enabled": False,
            "grammar_enabled": False,
            "flashcards_enabled": False,
        }
        if initial_flags:
            self.flags.update(initial_flags)

    async def ensure_defaults(self) -> None:
        pass

    async def get_flags(self) -> dict[str, bool]:
        return dict(self.flags)

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        self.flags.update(flags)
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


class FakeUserRepository:
    """In-memory fake implementation of UserRepository."""

    def __init__(self) -> None:
        self.users: dict[str, object] = {}
        self.email_index: dict[str, str] = {}
        self.roles: dict[str, list[str]] = {}
        self.progress: dict[str, object] = {}

    async def get_by_id(self, user_id: str):
        return self.users.get(user_id)

    async def get_by_email(self, email: str):
        uid = self.email_index.get(email.strip().lower())
        return self.users.get(uid) if uid else None

    async def add(self, user) -> None:
        from jplearn_api.domain.errors import DuplicateEmailError

        if user.email in self.email_index:
            raise DuplicateEmailError("Email already registered")
        self.users[user.id] = user
        self.email_index[user.email] = user.id
        self.roles[user.id] = list(user.roles)

    async def update(self, user) -> None:
        if user.id in self.users:
            self.users[user.id] = user

    async def add_role(self, user_id: str, role: str) -> None:
        if user_id in self.roles:
            self.roles[user_id].append(role)
        else:
            self.roles[user_id] = [role]
        if user_id in self.users:
            self.users[user_id].roles = self.roles[user_id]

    async def add_initial_progress(self, user_id: str, now) -> None:
        self.progress[user_id] = {"now": now}


class FakeStoragePort:
    """In-memory fake storage port."""

    def __init__(self, existing_keys: set[str] | None = None) -> None:
        self.keys = set(existing_keys or ())

    async def stage(self, temp_key: str, stream) -> int:
        self.keys.add(temp_key)
        return 100

    async def promote(self, temp_key: str, final_key: str) -> None:
        self.keys.discard(temp_key)
        self.keys.add(final_key)

    async def delete(self, key: str) -> None:
        self.keys.discard(key)

    async def exists(self, key: str) -> bool:
        return key in self.keys

    async def check_readiness(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class FakeCatalogRepository:
    """In-memory fake implementation of CatalogRepository."""

    def __init__(self) -> None:
        self.items: dict[str, object] = {}
        self.topics: set[str] = {"topic_valid"}

    async def get_by_id(self, item_id: str):
        return self.items.get(item_id)

    async def add(self, item) -> None:
        self.items[item.id] = item

    async def update(self, item) -> None:
        self.items[item.id] = item

    async def topic_exists(self, topic_id: str) -> bool:
        return topic_id in self.topics


class FakeLearningRepository:
    """In-memory fake implementation of LearningRepository."""

    def __init__(self, initial_progress: dict[str, object] | None = None) -> None:
        self.sessions: dict[str, object] = {}
        self.progress: dict[str, object] = dict(initial_progress or {})
        self.devices: dict[tuple[str, str], object] = {}
        self.events: list[dict[str, object]] = []

    async def create_session(self, session) -> None:
        self.sessions[session.id] = session

    async def lock_and_get_session(self, session_id: str):
        return self.sessions.get(session_id)

    async def update_session(self, session) -> None:
        self.sessions[session.id] = session

    async def upsert_device(self, user_id: str, device_class: str, last_seen_at) -> None:
        self.devices[(user_id, device_class)] = last_seen_at

    async def get_progress(self, user_id: str):
        return self.progress.get(user_id)

    async def lock_and_get_progress(self, user_id: str):
        return self.progress.get(user_id)

    async def update_progress(self, progress) -> None:
        self.progress[progress.user_id] = progress

    async def record_event(
        self,
        user_id: str,
        session_id: str | None,
        event_type: str,
        payload: dict,
        created_at,
    ) -> None:
        self.events.append({
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": created_at,
        })

