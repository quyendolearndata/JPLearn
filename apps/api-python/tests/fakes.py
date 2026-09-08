"""Test fakes for Clean Architecture unit testing (Zero external I/O).

Provides transactional state isolation, deep-copying, and commit/rollback guarantees.
"""

from __future__ import annotations

import asyncio
import contextvars
import copy
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any
from uuid import uuid4

from jplearn_api.application.ports.ai_provider import (
    AiTranscriptionPort,
    AiTranscriptionResult,
    AiUsageRecord,
)
from jplearn_api.application.ports.repositories import (
    ApprovedSceneSearchResult,
    CatalogRepository,
    CollectionRepository,
    ContentJobRepository,
    ContentReportRepository,
    ContentRepository,
    FlagsRepository,
    LearningRepository,
    MediaRepository,
    PlaybackRepository,
    QuotaRepository,
    SavedSceneContext,
    SavedSceneProjection,
    SavedSceneRepository,
    SeriesRepository,
    TranscriptRepository,
    UsageLedgerRepository,
    UserRepository,
)
from jplearn_api.application.ports.security import MediaUrlSigner
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork, UnitOfWorkFactory
from jplearn_api.domain.collection import (
    CollectionDetail,
    CollectionSceneDetail,
    PersonalCollection,
)
from jplearn_api.domain.content_job import (
    ContentJob,
    ContentJobTask,
)
from jplearn_api.domain.content_report import (
    ContentReport,
    ContentReportAudit,
    ReportStatus,
)
from jplearn_api.domain.errors import ConflictError, EntityNotFoundError, RevisionConflictError
from jplearn_api.domain.playback import (
    DeletionStatus,
    HistoryDeletionJob,
    LearnerDailyActivity,
    LearnerPlaybackState,
    LearningPreferences,
    PlaybackCheckpoint,
    PlaybackReceipt,
    PlaybackSession,
    WatchHistoryItemProjection,
)
from jplearn_api.domain.quota import (
    AiUsageLedgerEntry,
    QuotaAccount,
)
from jplearn_api.domain.saved_scene import SavedScene, SceneAvailability
from jplearn_api.domain.search import (
    calculate_highlights_and_match_kind,
    decode_search_cursor,
    encode_search_cursor,
)
from jplearn_api.domain.transcript import (
    ApprovedSceneText,
    LanguageAnalysisJob,
    TranscriptRevision,
)

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

    async def inspect_media(self, key):
        import hashlib

        from jplearn_api.application.ports.media_probe import MediaInspection

        return MediaInspection(3_600_000, hashlib.sha256(self.files.get(key, b"fixture")).hexdigest())

    async def stage_stream(
        self, temp_key: str, stream: AsyncIterator[bytes], *, max_bytes: int = 500 * 1024 * 1024
    ) -> int:
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

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [key for key in self.keys if key.startswith(prefix)]

    async def check_ready(self) -> tuple[bool, str]:
        return True, "ok"

    async def check_readiness(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class FakeCatalogRepository(CatalogRepository):
    """In-memory fake implementation of CatalogRepository with transaction isolation."""

    def __init__(self, initial_items: dict[str, Any] | None = None) -> None:
        self._committed_items: dict[str, Any] = {k: copy.deepcopy(v) for k, v in (initial_items or {}).items()}
        self.items: dict[str, Any] = {k: copy.deepcopy(v) for k, v in (initial_items or {}).items()}
        self.topics: set[str] = {"topic_valid", "topic-1"}

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

    async def get_by_id_for_update(self, item_id: str) -> Any:
        return await self.get_by_id(item_id)

    async def update_draft_cas(
        self,
        item_id: str,
        expected_revision: int,
        topic_id: str,
        ci_level: int,
        duration_seconds: int,
        media_type: str,
        visual_support: str,
        title_internal: str,
    ) -> Any:
        from jplearn_api.application.ports.repositories import UpdateDraftResult, UpdateDraftResultStatus

        self._auto_register()
        item = self.items.get(item_id)
        if item is None:
            return UpdateDraftResult(status=UpdateDraftResultStatus.NOT_FOUND)
        if item.status != "draft":
            return UpdateDraftResult(status=UpdateDraftResultStatus.WRONG_STATUS, current_item=item)
        if item.revision != expected_revision:
            return UpdateDraftResult(status=UpdateDraftResultStatus.REVISION_CONFLICT, current_item=item)

        item.topic_id = topic_id
        item.ci_level = ci_level
        item.duration_seconds = duration_seconds
        item.media_type = media_type
        item.visual_support = visual_support
        item.title_internal = title_internal
        item.revision += 1
        return UpdateDraftResult(status=UpdateDraftResultStatus.SUCCESS, current_item=copy.deepcopy(item))

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

    async def list_published(
        self,
        ci_level: int | None = None,
        topic_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        self._auto_register()
        matched = []
        for item in self.items.values():
            if getattr(item, "status", None) != "published":
                continue
            if ci_level is not None and getattr(item, "ci_level", None) != ci_level:
                continue
            if topic_id is not None and getattr(item, "topic_id", None) != topic_id:
                continue
            matched.append(copy.deepcopy(item))
        matched.sort(key=lambda x: x.id)
        return matched[offset : offset + limit]


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

    async def get_session(self, session_id: str) -> Any:
        self._auto_register()
        return self.sessions.get(session_id)

    async def lock_and_get_session(self, session_id: str) -> Any:
        self._auto_register()
        return self.sessions.get(session_id)

    async def acquire_idempotency_lock(self, user_id: str, key: str) -> None:
        pass

    async def get_idempotency_session(self, user_id: str, key: str) -> tuple[str, str] | None:
        self._auto_register()
        if not hasattr(self, "idempotency"):
            self.idempotency = {}
        return self.idempotency.get((user_id, key))

    async def save_idempotency(self, user_id: str, key: str, session_id: str, request_hash: str) -> None:
        self._auto_register()
        if not hasattr(self, "idempotency"):
            self.idempotency = {}
        self.idempotency[(user_id, key)] = (session_id, request_hash)

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
        self.events.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "event_type": event_type,
                "payload": dict(payload),
                "created_at": created_at,
            }
        )
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

    async def get_catalog_item_status(self, catalog_item_id: str, *, for_update: bool = False) -> str | None:
        exists = await self.catalog_item_exists(catalog_item_id)
        if not exists:
            return None
        return getattr(self, "catalog_item_statuses", {}).get(catalog_item_id, "draft")

    async def list_all_storage_keys(self) -> set[str]:
        self._auto_register()
        return {getattr(a, "storage_key", "") for a in self.assets.values() if getattr(a, "storage_key", None)}

    async def storage_key_exists(self, storage_key: str) -> bool:
        self._auto_register()
        return any(getattr(a, "storage_key", None) == storage_key for a in self.assets.values())


class FakeContentRepository(ContentRepository):
    """In-memory fake implementation of ContentRepository with transaction isolation."""

    def __init__(self, initial_versions: dict[str, Any] | list[Any] | None = None) -> None:
        self._committed_versions: dict[str, list[Any]] = {}
        self.versions: dict[str, list[Any]] = {}
        if initial_versions:
            items = initial_versions.values() if isinstance(initial_versions, dict) else initial_versions
            for v in items:
                self._committed_versions.setdefault(v.catalog_item_id, []).append(copy.deepcopy(v))
            self.versions = copy.deepcopy(self._committed_versions)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.versions = copy.deepcopy(self._committed_versions)

    def commit_transaction(self) -> None:
        self._committed_versions = copy.deepcopy(self.versions)

    def rollback_transaction(self) -> None:
        self.versions = copy.deepcopy(self._committed_versions)

    async def get_published_by_catalog_item_id(self, catalog_item_id: str) -> Any:
        self._auto_register()
        versions = self.versions.get(catalog_item_id, [])
        for v in versions:
            if getattr(v, "is_published", False):
                return v
        return None

    async def get_current_draft_by_catalog_item_id(self, catalog_item_id: str) -> Any:
        self._auto_register()
        versions = self.versions.get(catalog_item_id, [])
        for v in versions:
            if not getattr(v, "is_published", False):
                return v
        return None

    async def get_by_id(self, version_id: str) -> Any:
        self._auto_register()
        for version_list in self.versions.values():
            for v in version_list:
                if v.id == version_id:
                    return copy.deepcopy(v)
        return None

    async def save_draft(self, content_version: Any) -> None:
        self._auto_register()
        item_versions = self.versions.setdefault(content_version.catalog_item_id, [])
        for idx, v in enumerate(item_versions):
            if v.id == content_version.id:
                item_versions[idx] = content_version
                return
        item_versions.append(content_version)

    async def update(self, content_version: Any) -> None:
        await self.save_draft(content_version)

    async def get_max_version_number(self, catalog_item_id: str) -> int:
        self._auto_register()
        versions = self.versions.get(catalog_item_id, [])
        if not versions:
            return 0
        return max((getattr(v, "version_number", 0) for v in versions), default=0)


class FakeSeriesRepository(SeriesRepository):
    """In-memory fake implementation of SeriesRepository with transaction isolation."""

    def __init__(self, initial_series: list[Any] | None = None) -> None:
        self._committed_series: dict[str, Any] = {s.id: copy.deepcopy(s) for s in (initial_series or [])}
        self.series: dict[str, Any] = {s.id: copy.deepcopy(s) for s in (initial_series or [])}

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.series = copy.deepcopy(self._committed_series)

    def commit_transaction(self) -> None:
        self._committed_series = copy.deepcopy(self.series)

    def rollback_transaction(self) -> None:
        self.series = copy.deepcopy(self._committed_series)

    async def get_by_id(self, series_id: str) -> Any:
        self._auto_register()
        s = self.series.get(series_id)
        return copy.deepcopy(s) if s else None

    async def get_by_id_for_update(self, series_id: str) -> Any:
        return await self.get_by_id(series_id)

    async def add(self, series: Any) -> None:
        self._auto_register()
        self.series[series.id] = copy.deepcopy(series)

    async def update(self, series: Any) -> None:
        self._auto_register()
        self.series[series.id] = copy.deepcopy(series)

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Any]:
        self._auto_register()
        res = list(self.series.values())
        if status:
            res = [s for s in res if s.status == status]
        if ci_level:
            res = [s for s in res if s.ci_level == ci_level]
        if topic_id:
            res = [s for s in res if s.topic_id == topic_id]
        res.sort(key=lambda s: getattr(s, "created_at", None) or "", reverse=True)
        return [copy.deepcopy(s) for s in res[offset : offset + limit]]

    async def list_published(
        self,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Any]:
        return await self.list_staff(
            status="published", ci_level=ci_level, topic_id=topic_id, offset=offset, limit=limit
        )

    async def get_published_catalog_item_ids(self, item_ids: list[str]) -> set[str]:
        self._auto_register()
        active = _active_fake_uow.get()
        if active is not None and hasattr(active, "catalog"):
            catalog_repo = active.catalog
            if hasattr(catalog_repo, "items"):
                res = set()
                for cid in item_ids:
                    item = catalog_repo.items.get(cid)
                    if item and getattr(item, "status", None) == "published":
                        res.add(cid)
                return res
        return set(item_ids)


class FakeSavedSceneRepository(SavedSceneRepository):
    """In-memory fake implementation of SavedSceneRepository with transaction isolation."""

    def __init__(self, initial_saved_scenes: list[SavedScene] | None = None) -> None:
        init_dict = {(s.user_id, s.scene_id): copy.deepcopy(s) for s in (initial_saved_scenes or [])}
        self._committed_saved_scenes: dict[tuple[str, str], SavedScene] = dict(init_dict)
        self.saved_scenes: dict[tuple[str, str], SavedScene] = dict(init_dict)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.saved_scenes = copy.deepcopy(self._committed_saved_scenes)

    def commit_transaction(self) -> None:
        self._committed_saved_scenes = copy.deepcopy(self.saved_scenes)

    def rollback_transaction(self) -> None:
        self.saved_scenes = copy.deepcopy(self._committed_saved_scenes)

    async def get(self, user_id: str, scene_id: str) -> SavedScene | None:
        self._auto_register()
        val = self.saved_scenes.get((user_id, scene_id))
        return copy.deepcopy(val) if val else None

    async def add(self, saved_scene: SavedScene) -> None:
        self._auto_register()
        self.saved_scenes[(saved_scene.user_id, saved_scene.scene_id)] = copy.deepcopy(saved_scene)
        if _active_fake_uow.get() is None:
            self._committed_saved_scenes[(saved_scene.user_id, saved_scene.scene_id)] = copy.deepcopy(saved_scene)

    async def delete(self, user_id: str, scene_id: str) -> bool:
        self._auto_register()
        key = (user_id, scene_id)
        if key in self.saved_scenes:
            del self.saved_scenes[key]
            if _active_fake_uow.get() is None:
                self._committed_saved_scenes.pop(key, None)
            return True
        return False

    async def get_scene_context(self, scene_id: str) -> SavedSceneContext | None:
        self._auto_register()
        active = _active_fake_uow.get()
        if active is None or not hasattr(active, "content") or not hasattr(active, "catalog"):
            return None
        content_repo = active.content
        catalog_repo = active.catalog

        target_scene = None
        target_version = None
        all_versions = [
            v
            for sublist in getattr(content_repo, "versions", {}).values()
            for v in (sublist if isinstance(sublist, list) else [sublist])
        ]
        for version in all_versions:
            for sc in getattr(version, "scenes", []):
                if sc.id == scene_id:
                    target_scene = sc
                    target_version = version
                    break
            if target_scene:
                break

        if not target_scene or not target_version:
            return None

        catalog_item = getattr(catalog_repo, "items", {}).get(target_version.catalog_item_id)
        if not catalog_item:
            return None

        published_versions = [v for v in all_versions if v.catalog_item_id == catalog_item.id and v.is_published]
        published_versions.sort(key=lambda v: getattr(v, "version_number", 0), reverse=True)
        is_current_published = bool(published_versions and published_versions[0].id == target_version.id)

        return SavedSceneContext(
            scene_id=scene_id,
            content_version_id=target_version.id,
            is_version_published=target_version.is_published,
            catalog_item_id=catalog_item.id,
            catalog_status=catalog_item.status,
            is_current_published_version=is_current_published,
        )

    async def list_projections_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[SavedSceneProjection], int]:
        self._auto_register()
        active = _active_fake_uow.get()
        user_saved = [s for s in self.saved_scenes.values() if s.user_id == user_id]
        user_saved.sort(key=lambda s: (s.saved_at, s.id), reverse=True)
        total = len(user_saved)
        page = user_saved[offset : offset + limit]

        content_repo = getattr(active, "content", None)
        catalog_repo = getattr(active, "catalog", None)

        all_versions = []
        if content_repo:
            all_versions = [
                v
                for sublist in getattr(content_repo, "versions", {}).values()
                for v in (sublist if isinstance(sublist, list) else [sublist])
            ]

        projections: list[SavedSceneProjection] = []
        for s in page:
            target_scene = None
            target_version = None
            for version in all_versions:
                for sc in getattr(version, "scenes", []):
                    if sc.id == s.scene_id:
                        target_scene = sc
                        target_version = version
                        break
                if target_scene:
                    break

            catalog_item = None
            if target_version and catalog_repo:
                catalog_item = getattr(catalog_repo, "items", {}).get(target_version.catalog_item_id)

            if not target_scene or not target_version or not catalog_item or catalog_item.status != "published":
                availability = "unavailable"
                reason = "catalog_unpublished" if (catalog_item and catalog_item.status) else "scene_not_found"
                projections.append(
                    SavedSceneProjection(
                        id=s.id,
                        scene_id=s.scene_id,
                        saved_at=s.saved_at,
                        availability=availability,
                        unavailable_reason=reason,
                        catalog_item_id=None,
                        content_version_id=None,
                        scene_index=None,
                        start_time_seconds=None,
                        end_time_seconds=None,
                        title_jp=None,
                        transcript_jp=None,
                    )
                )
            elif not target_version.is_published:
                availability = "unavailable"
                reason = "version_unpublished"
                projections.append(
                    SavedSceneProjection(
                        id=s.id,
                        scene_id=s.scene_id,
                        saved_at=s.saved_at,
                        availability=availability,
                        unavailable_reason=reason,
                        catalog_item_id=None,
                        content_version_id=None,
                        scene_index=None,
                        start_time_seconds=None,
                        end_time_seconds=None,
                        title_jp=None,
                        transcript_jp=None,
                    )
                )
            else:
                published_versions = [
                    v for v in all_versions if v.catalog_item_id == catalog_item.id and v.is_published
                ]
                published_versions.sort(key=lambda v: getattr(v, "version_number", 0), reverse=True)
                is_current = bool(published_versions and published_versions[0].id == target_version.id)
                availability = "available" if is_current else "stale_version"
                projections.append(
                    SavedSceneProjection(
                        id=s.id,
                        scene_id=s.scene_id,
                        saved_at=s.saved_at,
                        availability=availability,
                        unavailable_reason=None,
                        catalog_item_id=catalog_item.id,
                        content_version_id=target_version.id,
                        scene_index=target_scene.scene_index,
                        start_time_seconds=target_scene.start_time_seconds,
                        end_time_seconds=target_scene.end_time_seconds,
                        title_jp=target_scene.title_jp,
                        transcript_jp=target_scene.transcript_jp,
                    )
                )

        return projections, total


class FakeCollectionRepository(CollectionRepository):
    """In-memory fake implementation of CollectionRepository with transaction isolation."""

    def __init__(self, initial_collections: list[PersonalCollection] | None = None) -> None:
        self._committed_collections: dict[str, dict[str, Any]] = {}
        for c in initial_collections or []:
            self._committed_collections[c.id] = {
                "collection": copy.deepcopy(c),
                "idempotency_key": None,
                "request_hash": None,
            }
        self.collections: dict[str, dict[str, Any]] = copy.deepcopy(self._committed_collections)
        self._committed_scenes: dict[str, list[dict[str, Any]]] = {}
        self.collection_scenes: dict[str, list[dict[str, Any]]] = copy.deepcopy(self._committed_scenes)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.collections = copy.deepcopy(self._committed_collections)
        self.collection_scenes = copy.deepcopy(self._committed_scenes)

    def commit_transaction(self) -> None:
        self._committed_collections = copy.deepcopy(self.collections)
        self._committed_scenes = copy.deepcopy(self.collection_scenes)

    def rollback_transaction(self) -> None:
        self.collections = copy.deepcopy(self._committed_collections)
        self.collection_scenes = copy.deepcopy(self._committed_scenes)

    async def acquire_library_lock(self, user_id: str) -> None:
        self._auto_register()

    async def get_by_id(self, user_id: str, collection_id: str) -> PersonalCollection | None:
        self._auto_register()
        data = self.collections.get(collection_id)
        if not data or data["collection"].user_id != user_id:
            return None
        c = copy.deepcopy(data["collection"])
        scenes = self.collection_scenes.get(collection_id, [])
        c.scene_count = len(scenes)
        return c

    async def get_detail(self, user_id: str, collection_id: str) -> CollectionDetail | None:
        self._auto_register()
        data = self.collections.get(collection_id)
        if not data or data["collection"].user_id != user_id:
            return None
        coll = data["collection"]
        scenes = self.collection_scenes.get(collection_id, [])

        active = _active_fake_uow.get()
        content_repo = getattr(active, "content", None) if active else None
        catalog_repo = getattr(active, "catalog", None) if active else None

        all_versions = []
        if content_repo:
            for sublist in getattr(content_repo, "versions", {}).values():
                all_versions.extend(sublist if isinstance(sublist, list) else [sublist])

        scene_details: list[CollectionSceneDetail] = []
        for s in scenes:
            scene_id = s["scene_id"]
            position = s["position"]
            added_at = s["added_at"]

            target_scene = None
            target_version = None
            for v in all_versions:
                for sc in getattr(v, "scenes", []):
                    if sc.id == scene_id:
                        target_scene = sc
                        target_version = v
                        break
                if target_scene:
                    break

            catalog_item = (
                getattr(catalog_repo, "items", {}).get(target_version.catalog_item_id)
                if target_version and catalog_repo
                else None
            )

            if not target_scene or not target_version or not catalog_item or catalog_item.status != "published":
                scene_details.append(
                    CollectionSceneDetail(
                        position=position,
                        scene_id=scene_id,
                        availability=SceneAvailability.UNAVAILABLE,
                        scene=None,
                        reason="catalog_unpublished" if catalog_item else "scene_not_found",
                        added_at=added_at,
                    )
                )
            else:
                published_versions = [
                    v for v in all_versions if v.catalog_item_id == catalog_item.id and v.is_published
                ]
                published_versions.sort(key=lambda v: getattr(v, "version_number", 0), reverse=True)
                is_current = bool(published_versions and published_versions[0].id == target_version.id)
                avail = SceneAvailability.AVAILABLE if is_current else SceneAvailability.STALE_VERSION
                scene_details.append(
                    CollectionSceneDetail(
                        position=position,
                        scene_id=scene_id,
                        availability=avail,
                        scene={
                            "catalog_item_id": catalog_item.id,
                            "content_version_id": target_version.id,
                            "scene_index": target_scene.scene_index,
                            "start_time_seconds": target_scene.start_time_seconds,
                            "end_time_seconds": target_scene.end_time_seconds,
                            "title_jp": target_scene.title_jp,
                            "transcript_jp": target_scene.transcript_jp,
                        },
                        reason=None if is_current else "new_version_available",
                        added_at=added_at,
                    )
                )

        return CollectionDetail(
            id=coll.id,
            user_id=coll.user_id,
            name=coll.name,
            revision=coll.revision,
            scene_count=len(scene_details),
            created_at=coll.created_at,
            updated_at=coll.updated_at,
            scenes=scene_details,
        )

    async def find_by_idempotency_key(self, user_id: str, key: str) -> tuple[PersonalCollection, str | None] | None:
        self._auto_register()
        for data in self.collections.values():
            if data["collection"].user_id == user_id and data["idempotency_key"] == key:
                c = copy.deepcopy(data["collection"])
                scenes = self.collection_scenes.get(c.id, [])
                c.scene_count = len(scenes)
                return c, data["request_hash"]
        return None

    async def count_by_user(self, user_id: str) -> int:
        self._auto_register()
        return sum(1 for d in self.collections.values() if d["collection"].user_id == user_id)

    async def create(
        self,
        collection: PersonalCollection,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> PersonalCollection:
        self._auto_register()
        c = copy.deepcopy(collection)
        self.collections[c.id] = {
            "collection": c,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
        }
        self.collection_scenes[c.id] = []
        if _active_fake_uow.get() is None:
            self._committed_collections[c.id] = copy.deepcopy(self.collections[c.id])
            self._committed_scenes[c.id] = []
        return copy.deepcopy(c)

    async def list_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PersonalCollection], int]:
        self._auto_register()
        user_colls = [d["collection"] for d in self.collections.values() if d["collection"].user_id == user_id]
        user_colls.sort(key=lambda c: (c.created_at, c.id), reverse=True)
        total = len(user_colls)
        sliced = user_colls[offset : offset + limit]
        result = []
        for c in sliced:
            cp = copy.deepcopy(c)
            scenes = self.collection_scenes.get(cp.id, [])
            cp.scene_count = len(scenes)
            result.append(cp)
        return result, total

    async def update_name(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        new_name: str,
    ) -> PersonalCollection:
        self._auto_register()
        data = self.collections.get(collection_id)
        if not data or data["collection"].user_id != user_id:
            raise EntityNotFoundError(f"Collection {collection_id} not found")
        c = data["collection"]
        if c.revision != expected_revision:
            raise ConflictError(f"Collection revision conflict: expected {expected_revision}, current {c.revision}")
        c.name = new_name
        c.revision += 1
        c.updated_at = datetime.now(UTC)
        scenes = self.collection_scenes.get(c.id, [])
        cp = copy.deepcopy(c)
        cp.scene_count = len(scenes)
        if _active_fake_uow.get() is None:
            self._committed_collections[collection_id] = copy.deepcopy(self.collections[collection_id])
        return cp

    async def replace_scenes(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        scene_ids: list[str],
    ) -> PersonalCollection:
        self._auto_register()
        data = self.collections.get(collection_id)
        if not data or data["collection"].user_id != user_id:
            raise EntityNotFoundError(f"Collection {collection_id} not found")
        c = data["collection"]
        if c.revision != expected_revision:
            raise ConflictError(f"Collection revision conflict: expected {expected_revision}, current {c.revision}")
        now = datetime.now(UTC)
        self.collection_scenes[collection_id] = [
            {"scene_id": sid, "position": pos, "added_at": now} for pos, sid in enumerate(scene_ids)
        ]
        c.revision += 1
        c.updated_at = now
        cp = copy.deepcopy(c)
        cp.scene_count = len(scene_ids)
        if _active_fake_uow.get() is None:
            self._committed_collections[collection_id] = copy.deepcopy(self.collections[collection_id])
            self._committed_scenes[collection_id] = copy.deepcopy(self.collection_scenes[collection_id])
        return cp

    async def delete(self, user_id: str, collection_id: str) -> bool:
        self._auto_register()
        data = self.collections.get(collection_id)
        if not data or data["collection"].user_id != user_id:
            return False
        del self.collections[collection_id]
        if collection_id in self.collection_scenes:
            del self.collection_scenes[collection_id]
        if _active_fake_uow.get() is None:
            self._committed_collections.pop(collection_id, None)
            self._committed_scenes.pop(collection_id, None)
        return True

    async def bump_revisions_for_scenes(self, user_id: str, scene_ids: list[str]) -> list[str]:
        self._auto_register()
        affected = []
        target_scenes = set(scene_ids)
        now = datetime.now(UTC)
        for coll_id, sc_list in list(self.collection_scenes.items()):
            data = self.collections.get(coll_id)
            if not data or data["collection"].user_id != user_id:
                continue
            if any(s["scene_id"] in target_scenes for s in sc_list):
                affected.append(coll_id)
                self.collection_scenes[coll_id] = [s for s in sc_list if s["scene_id"] not in target_scenes]
                for i, s in enumerate(self.collection_scenes[coll_id]):
                    s["position"] = i
                data["collection"].revision += 1
                data["collection"].updated_at = now
        return affected


class FakeContentReportRepository(ContentReportRepository):
    """In-memory fake implementation of ContentReportRepository with transaction isolation."""

    def __init__(self) -> None:
        self._committed_reports: dict[str, dict[str, Any]] = {}
        self.reports: dict[str, dict[str, Any]] = {}
        self._committed_audits: dict[str, list[ContentReportAudit]] = {}
        self.audits: dict[str, list[ContentReportAudit]] = {}
        self._uow: FakeUnitOfWork | None = None

    def bind_uow(self, uow: FakeUnitOfWork) -> None:
        self._uow = uow

    def _auto_register(self) -> None:
        if self._uow is not None:
            self._uow.register(self)
        active = _active_fake_uow.get()
        if active is not None and self not in active.participants:
            active.register(self)

    def begin_transaction(self) -> None:
        self.reports = copy.deepcopy(self._committed_reports)
        self.audits = copy.deepcopy(self._committed_audits)

    def commit_transaction(self) -> None:
        self._committed_reports = copy.deepcopy(self.reports)
        self._committed_audits = copy.deepcopy(self.audits)

    def rollback_transaction(self) -> None:
        self.reports = copy.deepcopy(self._committed_reports)
        self.audits = copy.deepcopy(self._committed_audits)

    async def get_by_id(self, report_id: str) -> ContentReport | None:
        self._auto_register()
        item = self.reports.get(report_id)
        if not item:
            return None
        return copy.deepcopy(item["report"])

    async def get_by_id_for_user(self, user_id: str, report_id: str) -> ContentReport | None:
        self._auto_register()
        item = self.reports.get(report_id)
        if not item or item["report"].user_id != user_id:
            return None
        return copy.deepcopy(item["report"])

    async def find_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> tuple[ContentReport, str | None] | None:
        self._auto_register()
        for item in self.reports.values():
            r = item["report"]
            if r.user_id == user_id and r.idempotency_key == idempotency_key:
                return copy.deepcopy(r), item.get("request_hash")
        return None

    async def count_today_by_user(self, user_id: str, start_of_day: datetime) -> int:
        self._auto_register()
        count = 0
        sod = start_of_day.replace(tzinfo=UTC) if start_of_day.tzinfo is None else start_of_day
        for item in self.reports.values():
            r = item["report"]
            if r.user_id == user_id:
                dt = r.created_at.replace(tzinfo=UTC) if r.created_at.tzinfo is None else r.created_at
                if dt >= sod:
                    count += 1
        return count

    async def create(
        self,
        report: ContentReport,
        request_hash: str | None = None,
    ) -> ContentReport:
        self._auto_register()
        if report.idempotency_key:
            for item in self.reports.values():
                r = item["report"]
                if r.user_id == report.user_id and r.idempotency_key == report.idempotency_key:
                    raise ConflictError(f"Duplicate idempotency key {report.idempotency_key}")
        self.reports[report.id] = {
            "report": copy.deepcopy(report),
            "request_hash": request_hash,
        }
        return copy.deepcopy(report)

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]:
        self._auto_register()
        user_reports = [
            copy.deepcopy(item["report"]) for item in self.reports.values() if item["report"].user_id == user_id
        ]
        user_reports.sort(key=lambda x: (x.created_at, x.id), reverse=True)
        total = len(user_reports)
        return user_reports[offset : offset + limit], total

    async def list_staff(
        self,
        status: str | None = None,
        category: str | None = None,
        catalog_item_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]:
        self._auto_register()
        filtered = []
        for item in self.reports.values():
            r = item["report"]
            st = r.status.value if hasattr(r.status, "value") else r.status
            cat = r.category.value if hasattr(r.category, "value") else r.category
            if status and st != status:
                continue
            if category and cat != category:
                continue
            if catalog_item_id and r.catalog_item_id != catalog_item_id:
                continue
            filtered.append(copy.deepcopy(r))
        filtered.sort(key=lambda x: (x.updated_at, x.id), reverse=True)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    async def get_audit_logs(self, report_id: str) -> list[ContentReportAudit]:
        self._auto_register()
        logs = [copy.deepcopy(a) for a in self.audits.get(report_id, [])]
        logs.sort(key=lambda x: (x.created_at, x.revision))
        return logs

    async def update_moderation(
        self,
        report_id: str,
        expected_revision: int,
        status: str | None = None,
        assignee_id: str | None = None,
        public_reply: str | None = None,
        internal_note: str | None = None,
        resolution_version_id: str | None = None,
        audit_actor_id: str | None = None,
        audit_reason: str | None = None,
    ) -> ContentReport:
        self._auto_register()
        item = self.reports.get(report_id)
        if not item:
            raise EntityNotFoundError(f"Content report '{report_id}' not found")
        r = item["report"]
        if r.revision != expected_revision:
            raise RevisionConflictError(f"Expected revision {expected_revision}, but current revision is {r.revision}")
        from_status = r.status
        now = datetime.now(UTC)
        if status is not None:
            r.status = ReportStatus(status) if isinstance(status, str) else status
        if assignee_id is not None:
            r.assignee_id = assignee_id if assignee_id != "" else None
        if public_reply is not None:
            r.public_reply = public_reply
        if internal_note is not None:
            r.internal_note = internal_note
        if resolution_version_id is not None:
            r.resolution_version_id = resolution_version_id if resolution_version_id != "" else None

        r.revision += 1
        r.updated_at = now

        if audit_actor_id:
            audit = ContentReportAudit(
                id=f"cra_{uuid4().hex[:16]}",
                report_id=report_id,
                actor_id=audit_actor_id,
                from_status=from_status,
                to_status=r.status,
                revision=r.revision,
                reason=audit_reason,
                created_at=now,
            )
            self.audits.setdefault(report_id, []).append(audit)

        return copy.deepcopy(r)


class FakePlaybackRepository(PlaybackRepository):
    """In-memory fake implementation of PlaybackRepository with transaction isolation."""

    def __init__(self) -> None:
        self._committed_playback_states: dict[str, LearnerPlaybackState] = {}
        self.playback_states: dict[str, LearnerPlaybackState] = {}
        self._committed_playbacks: dict[str, PlaybackSession] = {}
        self.playbacks: dict[str, PlaybackSession] = {}
        self._committed_receipts: dict[tuple[str, int], PlaybackReceipt] = {}
        self.receipts: dict[tuple[str, int], PlaybackReceipt] = {}
        self._committed_checkpoints: dict[tuple[str, str], PlaybackCheckpoint] = {}
        self.checkpoints: dict[tuple[str, str], PlaybackCheckpoint] = {}
        self._committed_preferences: dict[str, LearningPreferences] = {}
        self.preferences: dict[str, LearningPreferences] = {}
        self.preference_versions = {}
        self._committed_preference_versions = {}
        self.start_receipts = {}
        self._committed_start_receipts = {}
        self._committed_daily_activities: dict[tuple[str, str, int], LearnerDailyActivity] = {}
        self.daily_activities: dict[tuple[str, str, int], LearnerDailyActivity] = {}
        self._committed_history_deletions: dict[str, HistoryDeletionJob] = {}
        self.history_deletions: dict[str, HistoryDeletionJob] = {}
        self._uow: FakeUnitOfWork | None = None

    def bind_uow(self, uow: FakeUnitOfWork) -> None:
        self._uow = uow

    def _auto_register(self) -> None:
        if self._uow is not None:
            self._uow.register(self)
        active = _active_fake_uow.get()
        if active is not None and self not in active.participants:
            active.register(self)

    def begin_transaction(self) -> None:
        self.playback_states = copy.deepcopy(self._committed_playback_states)
        self.playbacks = copy.deepcopy(self._committed_playbacks)
        self.receipts = copy.deepcopy(self._committed_receipts)
        self.checkpoints = copy.deepcopy(self._committed_checkpoints)
        self.preferences = copy.deepcopy(self._committed_preferences)
        self.preference_versions = copy.deepcopy(self._committed_preference_versions)
        self.start_receipts = copy.deepcopy(self._committed_start_receipts)
        self.daily_activities = copy.deepcopy(self._committed_daily_activities)
        self.history_deletions = copy.deepcopy(self._committed_history_deletions)

    def commit_transaction(self) -> None:
        self._committed_start_receipts = copy.deepcopy(self.start_receipts)
        self._committed_playback_states = copy.deepcopy(self.playback_states)
        self._committed_playbacks = copy.deepcopy(self.playbacks)
        self._committed_receipts = copy.deepcopy(self.receipts)
        self._committed_checkpoints = copy.deepcopy(self.checkpoints)
        self._committed_preferences = copy.deepcopy(self.preferences)
        self._committed_preference_versions = copy.deepcopy(self.preference_versions)
        self._committed_daily_activities = copy.deepcopy(self.daily_activities)
        self._committed_history_deletions = copy.deepcopy(self.history_deletions)

    def rollback_transaction(self) -> None:
        self.playback_states = copy.deepcopy(self._committed_playback_states)
        self.playbacks = copy.deepcopy(self._committed_playbacks)
        self.receipts = copy.deepcopy(self._committed_receipts)
        self.checkpoints = copy.deepcopy(self._committed_checkpoints)
        self.preferences = copy.deepcopy(self._committed_preferences)
        self.preference_versions = copy.deepcopy(self._committed_preference_versions)
        self.start_receipts = copy.deepcopy(self._committed_start_receipts)
        self.daily_activities = copy.deepcopy(self._committed_daily_activities)
        self.history_deletions = copy.deepcopy(self._committed_history_deletions)

    async def acquire_learner_playback_lock(
        self,
        user_id: str,
        device_class: str,
        client_instance_id: str,
    ) -> LearnerPlaybackState:
        self._auto_register()
        now = datetime.now(UTC)
        if user_id not in self.playback_states:
            self.playback_states[user_id] = LearnerPlaybackState(
                user_id=user_id,
                active_playback_id=None,
                current_epoch=1,
                lease_expires_at=now,
                device_class=device_class,
                client_instance_id=client_instance_id,
                updated_at=now,
            )
            if _active_fake_uow.get() is None:
                self._committed_playback_states[user_id] = copy.deepcopy(self.playback_states[user_id])
        return copy.deepcopy(self.playback_states[user_id])

    async def update_learner_playback_state(self, state: LearnerPlaybackState) -> None:
        self._auto_register()
        self.playback_states[state.user_id] = copy.deepcopy(state)
        if _active_fake_uow.get() is None:
            self._committed_playback_states[state.user_id] = copy.deepcopy(state)

    async def get_playback(self, playback_id: str) -> PlaybackSession | None:
        self._auto_register()
        s = self.playbacks.get(playback_id)
        return copy.deepcopy(s) if s else None

    async def create_playback(self, session: PlaybackSession) -> PlaybackSession:
        self._auto_register()
        self.playbacks[session.id] = copy.deepcopy(session)
        if _active_fake_uow.get() is None:
            self._committed_playbacks[session.id] = copy.deepcopy(session)
        return copy.deepcopy(session)

    async def update_playback(self, session: PlaybackSession) -> None:
        self._auto_register()
        self.playbacks[session.id] = copy.deepcopy(session)
        if _active_fake_uow.get() is None:
            self._committed_playbacks[session.id] = copy.deepcopy(session)

    async def get_receipt(self, playback_id: str, seq: int) -> PlaybackReceipt | None:
        self._auto_register()
        r = self.receipts.get((playback_id, seq))
        return copy.deepcopy(r) if r else None

    async def save_receipt(self, receipt: PlaybackReceipt) -> None:
        self._auto_register()
        self.receipts[(receipt.playback_id, receipt.seq)] = copy.deepcopy(receipt)
        if _active_fake_uow.get() is None:
            self._committed_receipts[(receipt.playback_id, receipt.seq)] = copy.deepcopy(receipt)

    async def get_checkpoint(self, user_id: str, catalog_item_id: str) -> PlaybackCheckpoint | None:
        self._auto_register()
        c = self.checkpoints.get((user_id, catalog_item_id))
        return copy.deepcopy(c) if c else None

    async def save_checkpoint(self, checkpoint: PlaybackCheckpoint) -> None:
        self._auto_register()
        self.checkpoints[(checkpoint.user_id, checkpoint.catalog_item_id)] = copy.deepcopy(checkpoint)
        if _active_fake_uow.get() is None:
            self._committed_checkpoints[(checkpoint.user_id, checkpoint.catalog_item_id)] = copy.deepcopy(checkpoint)

    async def list_resume(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlaybackCheckpoint], int]:
        self._auto_register()
        user_cps = [copy.deepcopy(c) for (uid, _), c in self.checkpoints.items() if uid == user_id]
        user_cps.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(user_cps)
        return user_cps[offset : offset + limit], total

    async def get_learning_preferences(self, user_id: str) -> LearningPreferences:
        self._auto_register()
        p = self.preferences.get(user_id)
        if p:
            return copy.deepcopy(p)
        now = datetime.now(UTC)
        return LearningPreferences(
            user_id=user_id,
            daily_goal_minutes=15,
            preferred_topic_ids=[],
            timezone="Asia/Ho_Chi_Minh",
            revision=1,
            effective_at=now,
            created_at=now,
            updated_at=now,
        )

    async def get_start_receipt(self, user_id, key):
        self._auto_register()
        return copy.deepcopy(self.start_receipts.get((user_id, key)))

    async def save_start_receipt(self, user_id, key, request_hash, response):
        self._auto_register()
        self.start_receipts[(user_id, key)] = copy.deepcopy({"request_hash": request_hash, "response": response})

    async def get_effective_learning_preferences(self, user_id, at):
        self._auto_register()
        versions = [
            p
            for (uid, _), p in self.preference_versions.items()
            if uid == user_id and p.effective_at.replace(tzinfo=UTC) <= at.replace(tzinfo=UTC)
        ]
        if versions:
            return copy.deepcopy(max(versions, key=lambda p: (p.effective_at, p.revision)))
        return LearningPreferences(
            user_id=user_id,
            daily_goal_minutes=15,
            timezone="Asia/Ho_Chi_Minh",
            revision=1,
            effective_at=at,
            created_at=at,
            updated_at=at,
        )

    async def save_preference_version(self, pref):
        self._auto_register()
        self.preference_versions[(pref.user_id, pref.effective_at)] = copy.deepcopy(pref)
        if _active_fake_uow.get() is None:
            self._committed_preference_versions = copy.deepcopy(self.preference_versions)

    async def save_learning_preferences(self, pref: LearningPreferences) -> None:
        self._auto_register()
        self.preferences[pref.user_id] = copy.deepcopy(pref)
        if _active_fake_uow.get() is None:
            self._committed_preferences[pref.user_id] = copy.deepcopy(pref)

    async def record_daily_active_ms(
        self,
        user_id: str,
        date_str: str,
        timezone_str: str,
        delta_ms: int,
        goal_minutes: int,
        policy_revision: int = 1,
    ) -> LearnerDailyActivity:
        self._auto_register()
        key = (user_id, date_str, policy_revision)
        now = datetime.now(UTC)
        goal_ms = goal_minutes * 60 * 1000
        if key in self.daily_activities:
            act = copy.deepcopy(self.daily_activities[key])
            act.active_ms += delta_ms
            act.goal_met = act.goal_minutes > 0 and act.active_ms >= act.goal_minutes * 60000
            act.updated_at = now
            self.daily_activities[key] = act
        else:
            act = LearnerDailyActivity(
                user_id=user_id,
                date=date_str,
                policy_revision=policy_revision,
                timezone=timezone_str,
                active_ms=delta_ms,
                goal_minutes=goal_minutes,
                goal_met=(goal_ms > 0 and delta_ms >= goal_ms),
                updated_at=now,
            )
            self.daily_activities[key] = act
        if _active_fake_uow.get() is None:
            self._committed_daily_activities[key] = copy.deepcopy(act)
        return copy.deepcopy(act)

    async def get_daily_activity_range(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
    ) -> list[LearnerDailyActivity]:
        self._auto_register()
        matched: list[LearnerDailyActivity] = []
        for key, act in self.daily_activities.items():
            uid, d_str = key[0], key[1]
            if uid == user_id and from_date <= d_str <= to_date:
                matched.append(copy.deepcopy(act))
        matched.sort(key=lambda a: a.date)
        return matched

    async def get_latest_history_deletion_cutoff(self, user_id: str) -> datetime | None:
        self._auto_register()
        cutoffs = [
            j.cutoff_time
            for j in self.history_deletions.values()
            if j.user_id == user_id
            and (j.status.value if hasattr(j.status, "value") else str(j.status)) in ("queued", "running", "completed")
        ]
        return max(cutoffs) if cutoffs else None

    async def list_watch_history(
        self,
        user_id: str,
        cutoff_time: datetime | None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[WatchHistoryItemProjection], str | None]:
        self._auto_register()
        user_playbacks = [p for p in self.playbacks.values() if p.user_id == user_id]

        if cutoff_time is not None:
            c_unaware = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time
            user_playbacks = [
                p
                for p in user_playbacks
                if (p.created_at.replace(tzinfo=None) if p.created_at.tzinfo else p.created_at) > c_unaware
            ]

        # Sắp xếp giảm dần theo (created_at, id)
        user_playbacks.sort(
            key=lambda p: (
                p.created_at.replace(tzinfo=None) if p.created_at.tzinfo else p.created_at,
                p.id,
            ),
            reverse=True,
        )

        if cursor:
            try:
                parts = cursor.split("_", 1)
                cursor_ts = datetime.fromisoformat(parts[0])
                cursor_unaware = cursor_ts.replace(tzinfo=None) if cursor_ts.tzinfo else cursor_ts
                cursor_id = parts[1]
                filtered: list[PlaybackSession] = []
                for p in user_playbacks:
                    p_ts = p.created_at.replace(tzinfo=None) if p.created_at.tzinfo else p.created_at
                    if (p_ts < cursor_unaware) or (p_ts == cursor_unaware and p.id < cursor_id):
                        filtered.append(p)
                user_playbacks = filtered
            except Exception:
                pass

        selected = user_playbacks[:limit]
        items = [
            WatchHistoryItemProjection(
                playback_id=p.id,
                catalog_item_id=p.catalog_item_id,
                title_jp=f"Catalog Item {p.catalog_item_id}",
                item_type="video",
                topic_id="general",
                duration_seconds=600,
                status=p.status.value if hasattr(p.status, "value") else str(p.status),
                last_position_ms=p.last_position_ms,
                total_active_ms=p.total_active_ms,
                content_version_id=p.content_version_id,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in selected
        ]

        next_cursor = None
        if len(user_playbacks) > limit and selected:
            last_p = selected[-1]
            next_cursor = f"{last_p.created_at.isoformat()}_{last_p.id}"

        return items, next_cursor

    async def create_history_deletion_job(self, job: HistoryDeletionJob) -> HistoryDeletionJob:
        self._auto_register()
        self.history_deletions[job.id] = copy.deepcopy(job)
        if _active_fake_uow.get() is None:
            self._committed_history_deletions[job.id] = copy.deepcopy(job)
        return copy.deepcopy(job)

    async def get_history_deletion_job(self, job_id: str) -> HistoryDeletionJob | None:
        self._auto_register()
        j = self.history_deletions.get(job_id)
        return copy.deepcopy(j) if j else None

    async def claim_next_history_deletion_job(self) -> HistoryDeletionJob | None:
        self._auto_register()
        for j in self.history_deletions.values():
            status_val = j.status.value if hasattr(j.status, "value") else str(j.status)
            if status_val == "queued":
                j.status = DeletionStatus.RUNNING
                j.attempts += 1
                j.updated_at = datetime.now(UTC)
                if _active_fake_uow.get() is None:
                    self._committed_history_deletions[j.id] = copy.deepcopy(j)
                return copy.deepcopy(j)
        return None

    async def update_history_deletion_job(self, job: HistoryDeletionJob) -> None:
        self._auto_register()
        self.history_deletions[job.id] = copy.deepcopy(job)
        if _active_fake_uow.get() is None:
            self._committed_history_deletions[job.id] = copy.deepcopy(job)

    async def purge_watch_history_before_cutoff(self, user_id: str, cutoff_time: datetime) -> int:
        self._auto_register()
        c_unaware = cutoff_time.replace(tzinfo=None) if cutoff_time.tzinfo else cutoff_time

        to_delete_playbacks = [
            pid
            for pid, p in self.playbacks.items()
            if p.user_id == user_id
            and (p.created_at.replace(tzinfo=None) if p.created_at.tzinfo else p.created_at) <= c_unaware
        ]

        for pid in to_delete_playbacks:
            self.playbacks.pop(pid, None)

        # Xóa receipts của các playbacks bị xóa
        to_delete_receipts = [k for k in self.receipts.keys() if k[0] in to_delete_playbacks]
        for k in to_delete_receipts:
            self.receipts.pop(k, None)

        # Xóa checkpoints của user cập nhật trước cutoff
        to_delete_checkpoints = [
            k
            for k, cp in self.checkpoints.items()
            if cp.user_id == user_id
            and (cp.updated_at.replace(tzinfo=None) if cp.updated_at.tzinfo else cp.updated_at) <= c_unaware
        ]
        for k in to_delete_checkpoints:
            self.checkpoints.pop(k, None)

        if _active_fake_uow.get() is None:
            for pid in to_delete_playbacks:
                self._committed_playbacks.pop(pid, None)
            for k in to_delete_receipts:
                self._committed_receipts.pop(k, None)
            for k in to_delete_checkpoints:
                self._committed_checkpoints.pop(k, None)

        return len(to_delete_playbacks)


class FakeTranscriptRepository(TranscriptRepository):
    """In-memory fake implementation of TranscriptRepository with transaction isolation."""

    def __init__(self) -> None:
        self._committed_revisions: dict[tuple[str, str, int], TranscriptRevision] = {}
        self.revisions: dict[tuple[str, str, int], TranscriptRevision] = {}
        self._committed_approved_texts: dict[str, ApprovedSceneText] = {}
        self.approved_texts: dict[str, ApprovedSceneText] = {}
        self._committed_jobs: dict[str, LanguageAnalysisJob] = {}
        self.jobs: dict[str, LanguageAnalysisJob] = {}
        self._uow: FakeUnitOfWork | None = None

    def bind_uow(self, uow: FakeUnitOfWork) -> None:
        self._uow = uow

    def _auto_register(self) -> None:
        if self._uow is not None:
            self._uow.register(self)
        active = _active_fake_uow.get()
        if active is not None and self not in active.participants:
            active.register(self)

    def begin_transaction(self) -> None:
        self.revisions = copy.deepcopy(self._committed_revisions)
        self.approved_texts = copy.deepcopy(self._committed_approved_texts)
        self.jobs = copy.deepcopy(self._committed_jobs)

    def commit_transaction(self) -> None:
        self._committed_revisions = copy.deepcopy(self.revisions)
        self._committed_approved_texts = copy.deepcopy(self.approved_texts)
        self._committed_jobs = copy.deepcopy(self.jobs)

    def rollback_transaction(self) -> None:
        self.revisions = copy.deepcopy(self._committed_revisions)
        self.approved_texts = copy.deepcopy(self._committed_approved_texts)
        self.jobs = copy.deepcopy(self._committed_jobs)

    async def get_revision_by_id(self, revision_id: str) -> TranscriptRevision | None:
        self._auto_register()
        for r in self.revisions.values():
            if r.id == revision_id:
                return copy.deepcopy(r)
        return None

    async def get_latest_revision(self, catalog_item_id: str, content_version_id: str) -> TranscriptRevision | None:
        self._auto_register()
        revs = [
            r
            for r in self.revisions.values()
            if r.catalog_item_id == catalog_item_id and r.content_version_id == content_version_id
        ]
        if not revs:
            return None
        revs.sort(key=lambda x: x.revision, reverse=True)
        return copy.deepcopy(revs[0])

    async def get_by_revision(
        self, catalog_item_id: str, content_version_id: str, revision: int
    ) -> TranscriptRevision | None:
        self._auto_register()
        r = self.revisions.get((catalog_item_id, content_version_id, revision))
        return copy.deepcopy(r) if r else None

    async def save_revision(
        self,
        revision: TranscriptRevision,
        expected_revision: int | None = None,
    ) -> TranscriptRevision:
        self._auto_register()
        existing = None
        for r in self.revisions.values():
            if r.id == revision.id:
                existing = r
                break
        if existing is not None:
            exp_rev = (
                expected_revision
                if expected_revision is not None
                else (revision.revision - 1 if revision.revision > existing.revision else existing.revision)
            )
            if existing.revision != exp_rev:
                from jplearn_api.domain.errors import RevisionConflictError

                raise RevisionConflictError(
                    f"Atomic CAS failed for transcript '{revision.id}': "
                    f"expected revision {exp_rev}, found {existing.revision}"
                )
            self.revisions.pop((existing.catalog_item_id, existing.content_version_id, existing.revision), None)
        self.revisions[(revision.catalog_item_id, revision.content_version_id, revision.revision)] = copy.deepcopy(
            revision
        )
        return copy.deepcopy(revision)

    async def activate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
        transcript_revision_id: str,
        texts: list[ApprovedSceneText],
    ) -> None:
        self._auto_register()
        for t in self.approved_texts.values():
            if t.catalog_item_id == catalog_item_id and t.content_version_id == content_version_id:
                t.is_active = False
        for t in texts:
            self.approved_texts[t.id] = copy.deepcopy(t)

    async def deactivate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
    ) -> None:
        self._auto_register()
        for t in self.approved_texts.values():
            if t.catalog_item_id == catalog_item_id and t.content_version_id == content_version_id:
                t.is_active = False

    async def create_language_analysis_job(self, job: LanguageAnalysisJob) -> LanguageAnalysisJob:
        self._auto_register()
        self.jobs[job.id] = copy.deepcopy(job)
        return copy.deepcopy(job)

    async def get_language_analysis_job(self, job_id: str) -> LanguageAnalysisJob | None:
        self._auto_register()
        j = self.jobs.get(job_id)
        return copy.deepcopy(j) if j else None

    async def get_language_analysis_job_by_idempotency_key(
        self,
        catalog_item_id: str,
        idempotency_key: str,
    ) -> LanguageAnalysisJob | None:
        self._auto_register()
        for j in self.jobs.values():
            if j.catalog_item_id == catalog_item_id and j.idempotency_key == idempotency_key:
                return copy.deepcopy(j)
        return None

    async def search_approved_scenes(
        self,
        q: str,
        effective_max_ci: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[ApprovedSceneSearchResult], str | None, int]:
        self._auto_register()
        uow = self._uow or _active_fake_uow.get()

        # 1. Determine index generation
        active_approved = [t for t in self.approved_texts.values() if getattr(t, "is_active", True)]
        max_updated = max((t.updated_at for t in active_approved if t.updated_at), default=None)
        current_gen = str(int(max_updated.timestamp() * 1000)) if max_updated else "0"

        # 2. Decode cursor
        offset = 0
        if cursor:
            cursor_gen, cursor_offset = decode_search_cursor(cursor)
            if cursor_gen != current_gen:
                raise RevisionConflictError("Index generation mismatch, search results refreshed")
            offset = cursor_offset

        # 3. Filter candidates
        exact_matches: list[ApprovedSceneSearchResult] = []
        token_matches: list[ApprovedSceneSearchResult] = []

        for ast in active_approved:
            catalog_item = None
            content_version = None
            title_jp = "Scene"
            if uow:
                catalog_item = await uow.catalog.get_by_id(ast.catalog_item_id)
                content_version = await uow.content.get_by_id(ast.content_version_id)
                if content_version and hasattr(content_version, "scenes"):
                    for sc in content_version.scenes:
                        if sc.id == ast.scene_id:
                            title_jp = sc.title_jp
                            break

            # Filter: published catalog item & published version & ci_level <= effective_max_ci
            if catalog_item is None or catalog_item.status != "published":
                continue
            if content_version is None or not content_version.is_published:
                continue
            if catalog_item.ci_level > effective_max_ci:
                continue

            match_kind, spans = calculate_highlights_and_match_kind(ast.text_ja, q)
            if match_kind is None:
                continue

            item = ApprovedSceneSearchResult(
                catalog_item_id=ast.catalog_item_id,
                content_version_id=ast.content_version_id,
                scene_id=ast.scene_id,
                scene_index=ast.scene_index,
                start_time_seconds=ast.start_time_seconds,
                end_time_seconds=ast.end_time_seconds,
                matched_text_ja=ast.text_ja,
                highlight_spans=spans,
                match_kind=match_kind,
                ci_level=catalog_item.ci_level,
                topic_id=catalog_item.topic_id,
                title_jp=title_jp,
            )
            if match_kind == "exact_phrase":
                exact_matches.append(item)
            else:
                token_matches.append(item)

        exact_matches.sort(key=lambda x: (x.catalog_item_id, x.scene_index))
        token_matches.sort(key=lambda x: (x.catalog_item_id, x.scene_index))

        all_matches = exact_matches + token_matches
        total_estimated = len(all_matches)

        page = all_matches[offset : offset + limit]
        next_cursor = None
        if offset + limit < total_estimated:
            next_cursor = encode_search_cursor(current_gen, offset + limit)

        return page, next_cursor, total_estimated


class FakeQuotaRepository(QuotaRepository):
    """In-memory fake implementation of QuotaRepository with transaction isolation."""

    def __init__(self, initial_accounts: dict[str, QuotaAccount] | None = None) -> None:
        self._committed_accounts: dict[str, QuotaAccount] = {}
        self.accounts: dict[str, QuotaAccount] = {}
        if initial_accounts:
            for acc in initial_accounts.values():
                self._committed_accounts[acc.id] = copy.deepcopy(acc)
            self.accounts = copy.deepcopy(self._committed_accounts)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.accounts = copy.deepcopy(self._committed_accounts)

    def commit_transaction(self) -> None:
        self._committed_accounts = copy.deepcopy(self.accounts)

    def rollback_transaction(self) -> None:
        self.accounts = copy.deepcopy(self._committed_accounts)

    async def get_or_create_account_for_user(
        self,
        user_id: str,
        name: str = "Staff Default Quota",
    ) -> QuotaAccount:
        self._auto_register()
        for acc in self.accounts.values():
            if acc.user_id == user_id:
                return copy.deepcopy(acc)
        new_id = f"acc-{user_id}"
        acc = QuotaAccount(
            id=new_id,
            user_id=user_id,
            name=name,
            max_audio_seconds=3600,
            max_input_tokens=1000000,
            max_output_tokens=500000,
            max_cost_micros=10000000,
            is_active=True,
        )
        self.accounts[new_id] = acc
        return copy.deepcopy(acc)

    async def get_by_id(
        self,
        account_id: str,
        for_update: bool = False,
    ) -> QuotaAccount | None:
        self._auto_register()
        acc = self.accounts.get(account_id)
        if acc is None:
            return None
        return copy.deepcopy(acc)

    async def save_account(
        self,
        account: QuotaAccount,
    ) -> None:
        self._auto_register()
        self.accounts[account.id] = copy.deepcopy(account)


class FakeUsageLedgerRepository(UsageLedgerRepository):
    """In-memory fake implementation of UsageLedgerRepository with transaction isolation."""

    def __init__(self, initial_entries: dict[str, AiUsageLedgerEntry] | None = None) -> None:
        self._committed_entries: dict[str, AiUsageLedgerEntry] = {}
        self.entries: dict[str, AiUsageLedgerEntry] = {}
        if initial_entries:
            for entry in initial_entries.values():
                self._committed_entries[entry.id] = copy.deepcopy(entry)
            self.entries = copy.deepcopy(self._committed_entries)

    def _auto_register(self) -> None:
        active = _active_fake_uow.get()
        if active is not None:
            active.register(self)

    def begin_transaction(self) -> None:
        self.entries = copy.deepcopy(self._committed_entries)

    def commit_transaction(self) -> None:
        self._committed_entries = copy.deepcopy(self.entries)

    def rollback_transaction(self) -> None:
        self.entries = copy.deepcopy(self._committed_entries)

    async def add_entry(
        self,
        entry: AiUsageLedgerEntry,
    ) -> None:
        self._auto_register()
        self.entries[entry.id] = copy.deepcopy(entry)

    async def get_entry_by_id(
        self,
        entry_id: str,
    ) -> AiUsageLedgerEntry | None:
        self._auto_register()
        entry = self.entries.get(entry_id)
        if entry is None:
            return None
        return copy.deepcopy(entry)

    async def get_by_idempotency_key(
        self,
        account_id: str,
        idempotency_key: str,
        kind: str,
    ) -> AiUsageLedgerEntry | None:
        self._auto_register()
        for e in self.entries.values():
            if e.account_id == account_id and e.idempotency_key == idempotency_key and e.kind == kind:
                return copy.deepcopy(e)
        return None

    async def get_reservation_by_job_id(self, job_id: str) -> AiUsageLedgerEntry | None:
        self._auto_register()
        for e in self.entries.values():
            if e.job_id == job_id and e.kind == "reservation":
                return copy.deepcopy(e)
        return None

    async def get_settlement(
        self,
        provider: str,
        provider_request_id: str,
        attempt: int,
        kind: str = "settlement",
    ) -> AiUsageLedgerEntry | None:
        self._auto_register()
        for e in self.entries.values():
            if (
                e.provider == provider
                and e.provider_request_id == provider_request_id
                and e.attempt == attempt
                and e.kind == kind
            ):
                return copy.deepcopy(e)
        return None

    async def list_user_usage(
        self,
        user_id: str,
        from_date: datetime,
        to_date: datetime,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AiUsageLedgerEntry], int]:
        self._auto_register()
        matched = [e for e in self.entries.values() if e.user_id == user_id and from_date <= e.created_at <= to_date]
        matched.sort(key=lambda x: x.created_at, reverse=True)
        total = len(matched)
        page = matched[offset : offset + limit]
        return [copy.deepcopy(e) for e in page], total

    async def get_summary(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        self._auto_register()
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for e in self.entries.values():
            if e.kind == "settlement" and from_date <= e.created_at <= to_date:
                dt_str = e.created_at.strftime("%Y-%m-%d")
                key = (e.provider, e.currency, dt_str)
                if key not in groups:
                    groups[key] = {
                        "provider": e.provider,
                        "currency": e.currency,
                        "date": dt_str,
                        "total_audio_seconds": 0,
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_cost_micros": 0,
                        "events_count": 0,
                    }
                groups[key]["total_audio_seconds"] += e.audio_seconds
                groups[key]["total_input_tokens"] += e.input_tokens
                groups[key]["total_output_tokens"] += e.output_tokens
                groups[key]["total_cost_micros"] += e.cost_micros
                groups[key]["events_count"] += 1
        return sorted(groups.values(), key=lambda x: (x["date"], x["provider"]), reverse=True)


class FakeContentJobRepository(ContentJobRepository):
    """In-memory content job repository with transactional isolation."""

    def __init__(self) -> None:
        self.jobs: dict[str, ContentJob] = {}
        self._committed_jobs: dict[str, ContentJob] = {}
        self.attempts = {}
        self._committed_attempts = {}
        self._uow: FakeUnitOfWork | None = None

    def bind_uow(self, uow: FakeUnitOfWork) -> None:
        self._uow = uow

    def _auto_register(self) -> None:
        current_uow = _active_fake_uow.get()
        if current_uow is not None and self not in current_uow.participants:
            current_uow.register(self)

    def begin_transaction(self) -> None:
        self.jobs = copy.deepcopy(self._committed_jobs)
        self.attempts = copy.deepcopy(self._committed_attempts)

    def commit_transaction(self) -> None:
        self._committed_jobs = copy.deepcopy(self.jobs)
        self._committed_attempts = copy.deepcopy(self.attempts)

    def rollback_transaction(self) -> None:
        self.jobs = copy.deepcopy(self._committed_jobs)
        self.attempts = copy.deepcopy(self._committed_attempts)

    async def add(self, job: ContentJob) -> None:
        self._auto_register()
        self.jobs[job.id] = copy.deepcopy(job)

    async def get_by_id(self, job_id: str) -> ContentJob | None:
        self._auto_register()
        job = self.jobs.get(job_id)
        return copy.deepcopy(job) if job else None

    async def get_by_idempotency_key(
        self,
        created_by: str,
        idempotency_key: str,
    ) -> ContentJob | None:
        self._auto_register()
        for j in self.jobs.values():
            if j.created_by == created_by and j.idempotency_key == idempotency_key:
                return copy.deepcopy(j)
        return None

    async def find_active_job(
        self,
        content_version_id: str,
        task: ContentJobTask,
    ) -> ContentJob | None:
        self._auto_register()
        task_str = task.value if hasattr(task, "value") else str(task)
        for j in self.jobs.values():
            j_task = j.task.value if hasattr(j.task, "value") else str(j.task)
            j_status = j.status.value if hasattr(j.status, "value") else str(j.status)
            if j.content_version_id == content_version_id and j_task == task_str and j_status in ("queued", "running"):
                return copy.deepcopy(j)
        return None

    async def claim_next_queued_job(
        self,
        now: datetime,
        lease_duration_seconds: float,
        attempt_token: str,
    ) -> ContentJob | None:
        self._auto_register()
        candidates = []
        for j in self.jobs.values():
            if j.can_claim(now):
                candidates.append(j)
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.created_at)
        job = candidates[0]
        job.claim_lease(attempt_token, now + timedelta(seconds=lease_duration_seconds), now)
        return copy.deepcopy(job)

    async def update(self, job: ContentJob) -> None:
        self._auto_register()
        self.jobs[job.id] = copy.deepcopy(job)

    async def save_attempt(self, attempt):
        self._auto_register()
        self.attempts[attempt.id] = copy.deepcopy(attempt)

    async def get_attempt(self, attempt_id, for_update=False):
        self._auto_register()
        return copy.deepcopy(self.attempts.get(attempt_id))

    async def list_expired_attempts(self, now, limit=100):
        self._auto_register()
        return [a.id for a in self.attempts.values() if a.state == "running" and a.lease_expires_at <= now][:limit]

    async def list_job_attempts(self, job_id):
        self._auto_register()
        return [copy.deepcopy(a) for a in self.attempts.values() if a.job_id == job_id]


class FakeAiTranscriptionPort(AiTranscriptionPort):
    """In-memory configurable AI transcription port for testing."""

    def __init__(
        self,
        segments: list[dict[str, Any]] | None = None,
        usage: AiUsageRecord | None = None,
        exception_to_raise: Exception | None = None,
    ) -> None:
        self.segments = (
            segments
            if segments is not None
            else [{"scene_id": "scene-1", "text_ja": "こんにちは、世界！", "start_ms": 0, "end_ms": 2000}]
        )
        self.usage = usage or AiUsageRecord(
            audio_seconds=120,
            input_tokens=1000,
            output_tokens=300,
            cost_micros=150000,
            provider_request_id="req-fake-123",
            currency="USD",
            policy_version="v1",
        )
        self.exception_to_raise = exception_to_raise
        self.call_count = 0

    async def transcribe_and_segment(
        self,
        media_storage_key: str,
        media_duration_seconds: int,
        language: str = "ja",
    ) -> AiTranscriptionResult:
        self.call_count += 1
        if self.exception_to_raise is not None:
            raise self.exception_to_raise
        return AiTranscriptionResult(
            segments=self.segments,
            usage=self.usage,
            provenance={"provider": "fake_whisper", "model": "large-v3"},
        )


class FakeUnitOfWork(AsyncUnitOfWork):
    """In-memory Unit of Work recording commit/rollback actions with transactional state isolation."""

    def __init__(
        self,
        *participants: Any,
        users: UserRepository | None = None,
        catalog: CatalogRepository | None = None,
        content: ContentRepository | None = None,
        media: MediaRepository | None = None,
        learning: LearningRepository | None = None,
        flags: FlagsRepository | None = None,
        series: SeriesRepository | None = None,
        saved_scenes: SavedSceneRepository | None = None,
        collections: CollectionRepository | None = None,
        content_reports: ContentReportRepository | None = None,
        playbacks: PlaybackRepository | None = None,
        transcripts: TranscriptRepository | None = None,
        quota: QuotaRepository | None = None,
        usage_ledger: UsageLedgerRepository | None = None,
        content_jobs: ContentJobRepository | None = None,
    ) -> None:
        self.participants: list[Any] = list(participants)
        self.committed = False
        self.rolled_back = False
        self._reset_token: contextvars.Token | None = None
        self._cleanup = None

        resolved_users = users
        resolved_catalog = catalog
        resolved_content = content
        resolved_media = media
        resolved_learning = learning
        resolved_flags = flags
        resolved_series = series
        resolved_saved_scenes = saved_scenes
        resolved_collections = collections
        resolved_content_reports = content_reports
        resolved_playbacks = playbacks
        resolved_transcripts = transcripts
        resolved_quota = quota
        resolved_usage_ledger = usage_ledger
        resolved_content_jobs = content_jobs

        for p in self.participants:
            if isinstance(p, FakeUserRepository) and resolved_users is None:
                resolved_users = p
            elif isinstance(p, FakeCatalogRepository) and resolved_catalog is None:
                resolved_catalog = p
            elif isinstance(p, FakeContentRepository) and resolved_content is None:
                resolved_content = p
            elif isinstance(p, FakeMediaRepository) and resolved_media is None:
                resolved_media = p
            elif isinstance(p, FakeLearningRepository) and resolved_learning is None:
                resolved_learning = p
            elif isinstance(p, FakeFlagsRepository) and resolved_flags is None:
                resolved_flags = p
            elif isinstance(p, FakeSeriesRepository) and resolved_series is None:
                resolved_series = p
            elif isinstance(p, FakeSavedSceneRepository) and resolved_saved_scenes is None:
                resolved_saved_scenes = p
            elif isinstance(p, FakeCollectionRepository) and resolved_collections is None:
                resolved_collections = p
            elif isinstance(p, FakeContentReportRepository) and resolved_content_reports is None:
                resolved_content_reports = p
            elif isinstance(p, FakePlaybackRepository) and resolved_playbacks is None:
                resolved_playbacks = p
            elif isinstance(p, FakeTranscriptRepository) and resolved_transcripts is None:
                resolved_transcripts = p
            elif isinstance(p, FakeQuotaRepository) and resolved_quota is None:
                resolved_quota = p
            elif isinstance(p, FakeUsageLedgerRepository) and resolved_usage_ledger is None:
                resolved_usage_ledger = p
            elif isinstance(p, FakeContentJobRepository) and resolved_content_jobs is None:
                resolved_content_jobs = p

        self.users = resolved_users or FakeUserRepository()
        self.catalog = resolved_catalog or FakeCatalogRepository()
        self.content = resolved_content or FakeContentRepository()
        self.media = resolved_media or FakeMediaRepository()
        self.learning = resolved_learning or FakeLearningRepository()
        self.flags = resolved_flags or FakeFlagsRepository()
        self.series = resolved_series or FakeSeriesRepository()
        self.saved_scenes = resolved_saved_scenes or FakeSavedSceneRepository()
        self.collections = resolved_collections or FakeCollectionRepository()
        self.content_reports = resolved_content_reports or FakeContentReportRepository()
        self.playbacks = resolved_playbacks or FakePlaybackRepository()
        self.transcripts = resolved_transcripts or FakeTranscriptRepository()
        self.quota = resolved_quota or FakeQuotaRepository()
        self.usage_ledger = resolved_usage_ledger or FakeUsageLedgerRepository()
        self.content_jobs = resolved_content_jobs or FakeContentJobRepository()

        for repo in (
            self.users,
            self.catalog,
            self.content,
            self.media,
            self.learning,
            self.flags,
            self.series,
            self.saved_scenes,
            self.collections,
            self.content_reports,
            self.playbacks,
            self.transcripts,
            self.quota,
            self.usage_ledger,
            self.content_jobs,
        ):
            self.register(repo)

        for p in self.participants:
            if hasattr(p, "bind_uow"):
                p.bind_uow(self)
        self._depth = 0

    def own_cleanup(self, task: asyncio.Task[None]) -> None:
        self._cleanup = task

    def register(self, participant: Any) -> None:
        if participant not in self.participants:
            self.participants.append(participant)
            if hasattr(participant, "bind_uow"):
                participant.bind_uow(self)

    async def __aenter__(self) -> FakeUnitOfWork:
        self._depth += 1
        if self._depth > 1:
            return self
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
        self._depth -= 1
        if self._depth > 0:
            if exc_type is not None and not self.rolled_back:
                await self.rollback()
            return
        try:
            if self._cleanup is not None:
                cur_task = asyncio.current_task()
                cancelling_count = cur_task.cancelling() if (cur_task and hasattr(cur_task, "cancelling")) else 0
                if cancelling_count > 0:
                    for _ in range(cancelling_count):
                        cur_task.uncancel()
                try:
                    deadline = asyncio.get_running_loop().time() + 0.5
                    while not self._cleanup.done():
                        rem = deadline - asyncio.get_running_loop().time()
                        if rem <= 0:
                            break
                        try:
                            await asyncio.wait_for(asyncio.shield(self._cleanup), timeout=rem)
                        except (TimeoutError, asyncio.CancelledError):
                            break
                finally:
                    if cancelling_count > 0 and cur_task:
                        for _ in range(cancelling_count):
                            cur_task.cancel()
                if self._cleanup.done() and not self._cleanup.cancelled():
                    self._cleanup.result()
                return
            if (exc_type is not None or not self.committed) and not self.rolled_back:
                await self.rollback()
        except Exception:
            if exc_type is None:
                raise
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
        for p in self.participants:
            if hasattr(p, "rollback_transaction"):
                p.rollback_transaction()
        self.rolled_back = True


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


def create_fake_uow_factory(
    *participants: Any,
    users: UserRepository | None = None,
    catalog: CatalogRepository | None = None,
    content: ContentRepository | None = None,
    media: MediaRepository | None = None,
    learning: LearningRepository | None = None,
    flags: FlagsRepository | None = None,
    series: SeriesRepository | None = None,
    saved_scenes: SavedSceneRepository | None = None,
    collections: CollectionRepository | None = None,
    content_reports: ContentReportRepository | None = None,
    playbacks: PlaybackRepository | None = None,
    transcripts: TranscriptRepository | None = None,
    quota: QuotaRepository | None = None,
    usage_ledger: UsageLedgerRepository | None = None,
    content_jobs: ContentJobRepository | None = None,
) -> UnitOfWorkFactory:
    """Create a UnitOfWorkFactory producing fresh FakeUnitOfWork instances sharing the same committed state."""
    shared_users = users or FakeUserRepository()
    shared_catalog = catalog or FakeCatalogRepository()
    shared_content = content or FakeContentRepository()
    shared_media = media or FakeMediaRepository()
    shared_learning = learning or FakeLearningRepository()
    shared_flags = flags or FakeFlagsRepository()
    shared_series = series or FakeSeriesRepository()
    shared_saved_scenes = saved_scenes or FakeSavedSceneRepository()
    shared_collections = collections or FakeCollectionRepository()
    shared_content_reports = content_reports or FakeContentReportRepository()
    shared_playbacks = playbacks or FakePlaybackRepository()
    shared_transcripts = transcripts or FakeTranscriptRepository()
    shared_quota = quota or FakeQuotaRepository()
    shared_usage_ledger = usage_ledger or FakeUsageLedgerRepository()
    shared_content_jobs = content_jobs or FakeContentJobRepository()

    return lambda: FakeUnitOfWork(
        *participants,
        users=shared_users,
        catalog=shared_catalog,
        content=shared_content,
        media=shared_media,
        learning=shared_learning,
        flags=shared_flags,
        series=shared_series,
        saved_scenes=shared_saved_scenes,
        collections=shared_collections,
        content_reports=shared_content_reports,
        playbacks=shared_playbacks,
        transcripts=shared_transcripts,
        quota=shared_quota,
        usage_ledger=shared_usage_ledger,
        content_jobs=shared_content_jobs,
    )
