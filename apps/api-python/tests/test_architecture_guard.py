"""Architecture dependency guard enforcing Clean Architecture layer boundaries via AST."""

import ast
from pathlib import Path
import pytest

from jplearn_api.application.commands import UpdateFlagsCommand
from jplearn_api.application.handlers.flags import handle_get_flags, handle_update_flags
from fakes import FakeFlagsRepository, FakeUnitOfWork

ROOT_SRC = Path(__file__).resolve().parent.parent / "src" / "jplearn_api"


def get_all_imports(file_path: Path) -> list[str]:
    """Parse a python file using AST and collect all imported module names."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_domain_layer_dependencies():
    """Domain layer must be pure Python: no frameworks, no ORMs, no outer layers."""
    domain_dir = ROOT_SRC / "domain"
    forbidden_prefixes = (
        "jplearn_api.application",
        "jplearn_api.adapters",
        "jplearn_api.entrypoints",
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "asyncpg",
        "os",
    )

    violations = []
    for file_path in domain_dir.glob("**/*.py"):
        imports = get_all_imports(file_path)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.relative_to(ROOT_SRC)}: imports forbidden '{imp}'")

    assert not violations, f"Domain layer violations found:\n" + "\n".join(violations)


def test_application_layer_dependencies():
    """Application layer must not import adapters, entrypoints, frameworks or ORMs."""
    app_dir = ROOT_SRC / "application"
    forbidden_prefixes = (
        "jplearn_api.adapters",
        "jplearn_api.entrypoints",
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "asyncpg",
        "os",
    )

    violations = []
    for file_path in app_dir.glob("**/*.py"):
        imports = get_all_imports(file_path)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.relative_to(ROOT_SRC)}: imports forbidden '{imp}'")

    assert not violations, f"Application layer violations found:\n" + "\n".join(violations)


def test_adapters_layer_dependencies():
    """Adapters must not depend on entrypoints (HTTP/CLI controllers)."""
    adapters_dir = ROOT_SRC / "adapters"
    forbidden_prefixes = ("jplearn_api.entrypoints",)

    violations = []
    for file_path in adapters_dir.glob("**/*.py"):
        imports = get_all_imports(file_path)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    violations.append(f"{file_path.relative_to(ROOT_SRC)}: imports forbidden '{imp}'")

    assert not violations, f"Adapters layer violations found:\n" + "\n".join(violations)


@pytest.mark.asyncio
async def test_flags_use_case_in_memory():
    """Verify flags use case runs in pure memory with fake ports and zero I/O."""
    repo = FakeFlagsRepository({"speaking_enabled": False})
    uow = FakeUnitOfWork()

    initial = await handle_get_flags(repo)
    assert initial["speaking_enabled"] is False

    updated = await handle_update_flags(
        UpdateFlagsCommand(flags={"speaking_enabled": True}),
        uow=uow,
        repo=repo,
    )
    assert updated["speaking_enabled"] is True
    assert uow.committed is True


@pytest.mark.asyncio
async def test_identity_use_cases_in_memory():
    """Verify identity use cases run in pure memory with fake ports and zero I/O."""
    from fakes import FakePasswordHasher, FakeTokenService, FakeUserRepository
    from jplearn_api.application.commands import LogoutUserCommand, RegisterUserCommand
    from jplearn_api.application.handlers.identity import (
        handle_get_current_user,
        handle_login,
        handle_logout,
        handle_register,
    )
    from jplearn_api.application.queries import AuthenticateUserQuery, GetCurrentUserQuery
    from jplearn_api.domain.errors import DuplicateEmailError, InvalidDomainStateError, UnauthorizedError

    uow = FakeUnitOfWork()
    user_repo = FakeUserRepository()
    hasher = FakePasswordHasher()
    tokens = FakeTokenService()

    # 1. Register
    reg_cmd = RegisterUserCommand(email="test@example.com", password="password123", secret="sec")
    auth_dto = await handle_register(reg_cmd, uow, user_repo, hasher, tokens)
    assert auth_dto.user.email == "test@example.com"
    assert auth_dto.user.roles == ["learner"]
    assert uow.committed is True

    # 2. Duplicate registration fails closed
    with pytest.raises(DuplicateEmailError):
        await handle_register(reg_cmd, uow, user_repo, hasher, tokens)

    # 3. Password length check
    with pytest.raises(InvalidDomainStateError):
        await handle_register(RegisterUserCommand(email="a@b.com", password="short", secret="sec"), uow, user_repo, hasher, tokens)

    # 4. Login success
    login_query = AuthenticateUserQuery(email="test@example.com", password="password123", secret="sec")
    login_dto = await handle_login(login_query, user_repo, hasher, tokens)
    assert login_dto.user.id == auth_dto.user.id

    # 5. Login wrong password fails with UnauthorizedError
    with pytest.raises(UnauthorizedError):
        await handle_login(AuthenticateUserQuery(email="test@example.com", password="wrong", secret="sec"), user_repo, hasher, tokens)

    # 6. Get current user
    me_dto = await handle_get_current_user(GetCurrentUserQuery(user_id=auth_dto.user.id), user_repo)
    assert me_dto.email == "test@example.com"

    # 7. Logout
    logout_uow = FakeUnitOfWork()
    await handle_logout(LogoutUserCommand(user_id=auth_dto.user.id), logout_uow, user_repo)
    assert logout_uow.committed is True
    updated_user = await user_repo.get_by_id(auth_dto.user.id)
    assert updated_user.token_version == 1


@pytest.mark.asyncio
async def test_catalog_use_cases_in_memory():
    """Verify catalog state transitions in pure memory with fake ports."""
    from fakes import FakeCatalogRepository, FakeStoragePort
    from jplearn_api.application.commands import (
        ArchiveCatalogItemCommand,
        CreateCatalogItemCommand,
        PublishCatalogItemCommand,
        SubmitCatalogForQaCommand,
        UnpublishCatalogItemCommand,
    )
    from jplearn_api.application.handlers.catalog import (
        handle_archive,
        handle_create_catalog_item,
        handle_publish,
        handle_submit_qa,
        handle_unpublish,
    )
    from jplearn_api.domain.catalog import MediaRef
    from jplearn_api.domain.errors import InvalidDomainStateError, MediaInvariantError

    repo = FakeCatalogRepository()
    storage = FakeStoragePort()
    uow = FakeUnitOfWork()

    # 1. Create draft item
    cmd = CreateCatalogItemCommand(
        topic_id="topic_valid",
        ci_level=1,
        duration_seconds=120,
        media_type="video",
        visual_support="high",
        title_internal="Test Item",
        created_by="user1",
    )
    item_dto = await handle_create_catalog_item(cmd, uow, repo)
    assert item_dto.status == "draft"
    assert uow.committed is True

    # 2. Cannot publish directly from draft
    with pytest.raises(InvalidDomainStateError):
        await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)

    # 3. Submit QA
    qa_dto = await handle_submit_qa(SubmitCatalogForQaCommand(item_id=item_dto.id), uow, repo)
    assert qa_dto.status == "level_qa"

    # 4. Cannot publish without media
    with pytest.raises(MediaInvariantError):
        await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)

    # Attach media ref to domain item
    domain_item = await repo.get_by_id(item_dto.id)
    domain_item.media = [MediaRef(id="m1", storage_key="m1.bin")]

    # 5. Cannot publish if file missing on storage
    with pytest.raises(MediaInvariantError):
        await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)

    # Stage media to storage
    storage.keys.add("m1.bin")

    # 6. Publish succeeds
    pub_dto = await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)
    assert pub_dto.status == "published"

    # 7. Unpublish reverts to draft
    unpub_dto = await handle_unpublish(UnpublishCatalogItemCommand(item_id=item_dto.id), uow, repo)
    assert unpub_dto.status == "draft"

    # 8. Archive
    await handle_archive(ArchiveCatalogItemCommand(item_id=item_dto.id), uow, repo)
    archived_item = await repo.get_by_id(item_dto.id)
    assert archived_item.status == "archived"


@pytest.mark.asyncio
async def test_learning_use_cases_in_memory():
    """Verify learning session lifecycle and progress logic in pure memory."""
    from datetime import timedelta
    from fakes import FakeLearningRepository
    from jplearn_api.application.commands import EndLearningSessionCommand, StartLearningSessionCommand
    from jplearn_api.application.handlers.learning import (
        handle_end_session,
        handle_get_progress,
        handle_start_session,
    )
    from jplearn_api.application.queries import GetLearnerProgressQuery
    from jplearn_api.domain.errors import ForbiddenError, SessionAlreadyEndedError
    from jplearn_api.domain.learning import LearnerProgress

    initial_prog = LearnerProgress(user_id="user_learner", minutes_comprehensible=10, current_ci_level=1)
    repo = FakeLearningRepository(initial_progress={"user_learner": initial_prog})
    uow = FakeUnitOfWork()

    # 1. Start session
    start_cmd = StartLearningSessionCommand(user_id="user_learner", device_class="phone")
    session_dto = await handle_start_session(start_cmd, uow, repo)
    assert session_dto.device_class == "phone"
    assert session_dto.ended_at is None
    assert uow.committed is True
    assert len(repo.events) == 2  # session_started and level_exposed

    # 2. Get progress
    prog_dto = await handle_get_progress(GetLearnerProgressQuery(user_id="user_learner"), repo)
    assert prog_dto.minutes_comprehensible == 10

    # Simulate time elapsed: started 3 minutes ago
    domain_session = await repo.lock_and_get_session(session_dto.id)
    domain_session.started_at -= timedelta(seconds=185)

    # 3. End session by wrong user raises ForbiddenError
    with pytest.raises(ForbiddenError):
        await handle_end_session(EndLearningSessionCommand(user_id="other_user", session_id=session_dto.id), uow, repo)

    # 4. End session by owner succeeds exactly-once
    end_dto = await handle_end_session(EndLearningSessionCommand(user_id="user_learner", session_id=session_dto.id), uow, repo)
    assert end_dto.minutes_comprehensible == 13  # 10 + 3 minutes
    assert len(repo.events) == 4  # + session_ended and minutes_comprehensible

    # 5. Duplicate end session raises SessionAlreadyEndedError
    with pytest.raises(SessionAlreadyEndedError):
        await handle_end_session(EndLearningSessionCommand(user_id="user_learner", session_id=session_dto.id), uow, repo)


@pytest.mark.asyncio
async def test_media_use_cases_in_memory():
    """Verify media upload and HLS registration using in-memory fakes without PostgreSQL."""
    from collections.abc import AsyncIterator
    from fakes import FakeMediaRepository, FakeStoragePort
    from jplearn_api.application.handlers.media import (
        handle_register_hls,
        handle_upload_media,
    )
    from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError
    from jplearn_api.domain.range_parser import RangeNotSatisfiableError, parse_byte_range

    # 1. Pure domain range parser matrix
    assert parse_byte_range("bytes=0-1", 100) == (0, 1, 2)
    assert parse_byte_range("bytes=10-", 100) == (10, 99, 90)
    assert parse_byte_range("bytes=-10", 100) == (90, 99, 10)
    assert parse_byte_range("bytes=0-1, 2-3", 100) is None
    assert parse_byte_range("invalid", 100) is None
    with pytest.raises(RangeNotSatisfiableError):
        parse_byte_range("bytes=200-", 100)

    # 2. Setup media repository and storage
    media_repo = FakeMediaRepository(existing_items={"cat-item-1"})
    storage = FakeStoragePort()
    uow = FakeUnitOfWork()

    async def fake_stream() -> AsyncIterator[bytes]:
        yield b"additional video payload"

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    # 3. Upload to nonexistent catalog item raises EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        await handle_upload_media(
            catalog_item_id="missing-item",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="test.mp4",
            content_type="video/mp4",
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url="http://localhost:3001",
            secret="test-secret-at-least-32-bytes-long",
        )

    # 4. Upload with invalid extension raises InvalidDomainStateError
    with pytest.raises(InvalidDomainStateError):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="test.avi",
            content_type="video/mp4",
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url="http://localhost:3001",
            secret="test-secret-at-least-32-bytes-long",
        )

    # 5. Successful upload promotes object and creates record
    dto = await handle_upload_media(
        catalog_item_id="cat-item-1",
        first_chunk=valid_first_chunk,
        stream=fake_stream(),
        filename="video.mp4",
        content_type="video/mp4",
        uow=uow,
        media_repo=media_repo,
        storage=storage,
        base_url="http://localhost:3001",
        secret="test-secret-at-least-32-bytes-long",
    )
    assert dto.catalog_item_id == "cat-item-1"
    assert dto.mime == "video/mp4"
    assert dto.playback_url.startswith("http://localhost:3001/media/")
    assert uow.committed is True
    assert await storage.exists(f"{dto.id}.bin")

    # 6. Register HLS without manifest raises InvalidDomainStateError
    with pytest.raises(InvalidDomainStateError):
        await handle_register_hls(
            asset_id=dto.id,
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url="http://localhost:3001",
            secret="test-secret-at-least-32-bytes-long",
        )

    # 7. Register HLS with manifest succeeds
    storage.keys.add(f"hls/{dto.id}/index.m3u8")
    hls_dto = await handle_register_hls(
        asset_id=dto.id,
        uow=uow,
        media_repo=media_repo,
        storage=storage,
        base_url="http://localhost:3001",
        secret="test-secret-at-least-32-bytes-long",
    )
    assert hls_dto.hls_url is not None
    assert f"/media/{dto.id}/hls/index.m3u8" in hls_dto.hls_url
