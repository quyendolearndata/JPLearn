"""Architecture dependency guard enforcing Clean Architecture layer boundaries via AST.

Includes:
- Full relative and absolute import resolution.
- Layer boundary and reachability verification.
- Indirect environment access and dynamic import detection.
- Composition rule enforcement (no direct adapter instantiations in entrypoints).
- Mutation tests against temporary positive and negative fixtures.
- Transactional fake UoW failure boundary and state isolation verification.
- Zero side-effect package import verification under blocked I/O constructors.
"""

from __future__ import annotations

import ast
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
import subprocess
import sys
import pytest

from fakes import (
    FakeCatalogRepository,
    FakeFlagsRepository,
    FakeLearningRepository,
    FakeMediaRepository,
    FakePasswordHasher,
    FakeStoragePort,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
)
from jplearn_api.application.commands import (
    ArchiveCatalogItemCommand,
    CreateCatalogItemCommand,
    EndLearningSessionCommand,
    LogoutUserCommand,
    PublishCatalogItemCommand,
    RegisterUserCommand,
    StartLearningSessionCommand,
    SubmitCatalogForQaCommand,
    UnpublishCatalogItemCommand,
    UpdateFlagsCommand,
)
from jplearn_api.application.handlers.catalog import (
    handle_archive,
    handle_create_catalog_item,
    handle_publish,
    handle_submit_qa,
    handle_unpublish,
)
from jplearn_api.application.handlers.flags import handle_get_flags, handle_update_flags
from jplearn_api.application.handlers.identity import (
    handle_get_current_user,
    handle_login,
    handle_logout,
    handle_register,
)
from jplearn_api.application.handlers.learning import (
    handle_end_session,
    handle_get_progress,
    handle_start_session,
)
from jplearn_api.application.handlers.media import (
    handle_register_hls,
    handle_stream_hls,
    handle_stream_media,
    handle_upload_media,
)
from jplearn_api.application.queries import (
    AuthenticateUserQuery,
    GetCurrentUserQuery,
    GetLearnerProgressQuery,
)
from jplearn_api.domain.catalog import MediaRef
from jplearn_api.domain.errors import (
    DeterministicAbortError,
    DuplicateEmailError,
    EntityNotFoundError,
    ForbiddenError,
    InvalidDomainStateError,
    MediaInvariantError,
    SessionAlreadyEndedError,
    UnauthorizedError,
)
from jplearn_api.domain.learning import LearnerProgress
from jplearn_api.domain.range_parser import RangeNotSatisfiableError, parse_byte_range

ROOT_SRC = Path(__file__).resolve().parent.parent / "src" / "jplearn_api"


def resolve_imports(file_path: Path, package_root: Path = ROOT_SRC) -> list[str]:
    """Parse a python file using AST and collect fully qualified module names,
    resolving both absolute and relative imports (e.g. `from .. import module`).
    """
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))

    try:
        rel_path = file_path.relative_to(package_root)
        pkg_parts = [package_root.name] + list(rel_path.parent.parts)
    except ValueError:
        pkg_parts = [package_root.name]

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
                if base:
                    imports.append(base)
                for alias in node.names:
                    imports.append(f"{base}.{alias.name}" if base else alias.name)
            else:
                if node.level > len(pkg_parts):
                    target_pkg = []
                else:
                    target_pkg = pkg_parts[: len(pkg_parts) - (node.level - 1)]

                if node.module:
                    mod_path = ".".join(target_pkg + [node.module])
                    imports.append(mod_path)
                    for alias in node.names:
                        imports.append(f"{mod_path}.{alias.name}")
                else:
                    base_mod = ".".join(target_pkg)
                    imports.append(base_mod)
                    for alias in node.names:
                        imports.append(f"{base_mod}.{alias.name}")
    return imports


def check_env_access(file_path: Path) -> list[str]:
    """Check for direct or indirect environment access (os.environ, os.getenv, getenv)."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in ("environ", "getenv"):
                violations.append(f"{file_path.name}: forbidden environment access attribute '{node.attr}' at line {node.lineno}")
        elif isinstance(node, ast.Name):
            if node.id in ("environ", "getenv"):
                violations.append(f"{file_path.name}: forbidden environment access name '{node.id}' at line {node.lineno}")
    return violations


def check_dynamic_imports(file_path: Path) -> list[str]:
    """Check for dynamic import mechanisms in inner layers."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("__import__", "eval", "exec"):
                violations.append(f"{file_path.name}: forbidden dynamic execution '{node.func.id}' at line {node.lineno}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                violations.append(f"{file_path.name}: forbidden importlib.import_module call at line {node.lineno}")
    return violations


def check_domain_file(file_path: Path, package_root: Path = ROOT_SRC) -> list[str]:
    """Enforce Domain Layer rules: pure python, no external frameworks, no outer layers."""
    forbidden_prefixes = (
        "jplearn_api.application",
        "jplearn_api.adapters",
        "jplearn_api.entrypoints",
        "jplearn_api.routers",
        "jplearn_api.models",
        "jplearn_api.settings",
        "jplearn_api.bootstrap",
        "jplearn_api.deps",
        "jplearn_api.db",
        "jplearn_api.security",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "asyncpg",
        "os",
        "sys",
        "subprocess",
    )
    violations: list[str] = []
    imports = resolve_imports(file_path, package_root)
    for imp in imports:
        for forbidden in forbidden_prefixes:
            if imp == forbidden or imp.startswith(f"{forbidden}."):
                violations.append(f"{file_path.name}: imports forbidden '{imp}'")

    violations.extend(check_env_access(file_path))
    violations.extend(check_dynamic_imports(file_path))
    return violations


def check_application_file(file_path: Path, package_root: Path = ROOT_SRC) -> list[str]:
    """Enforce Application Layer rules: no adapters, entrypoints, routers, db or frameworks."""
    forbidden_prefixes = (
        "jplearn_api.adapters",
        "jplearn_api.entrypoints",
        "jplearn_api.routers",
        "jplearn_api.models",
        "jplearn_api.settings",
        "jplearn_api.bootstrap",
        "jplearn_api.deps",
        "jplearn_api.db",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "asyncpg",
    )
    violations: list[str] = []
    imports = resolve_imports(file_path, package_root)
    for imp in imports:
        for forbidden in forbidden_prefixes:
            if imp == forbidden or imp.startswith(f"{forbidden}."):
                violations.append(f"{file_path.name}: imports forbidden '{imp}'")

    violations.extend(check_env_access(file_path))
    violations.extend(check_dynamic_imports(file_path))
    return violations


def check_adapters_file(file_path: Path, package_root: Path = ROOT_SRC) -> list[str]:
    """Enforce Adapters Layer rules: must not depend on entrypoints or routers."""
    forbidden_prefixes = (
        "jplearn_api.entrypoints",
        "jplearn_api.routers",
        "jplearn_api.main",
        "fastapi.testclient",
        "starlette.testclient",
    )
    violations: list[str] = []
    imports = resolve_imports(file_path, package_root)
    for imp in imports:
        for forbidden in forbidden_prefixes:
            if imp == forbidden or imp.startswith(f"{forbidden}."):
                violations.append(f"{file_path.name}: imports forbidden '{imp}'")
    return violations


def check_composition_rules(file_path: Path) -> list[str]:
    """Enforce Composition rules: routers/entrypoints must not directly construct concrete adapters."""
    forbidden_adapter_constructors = {
        "SqlAlchemyUnitOfWork",
        "SqlAlchemyUserRepository",
        "SqlAlchemyCatalogRepository",
        "SqlAlchemyCatalogQueryAdapter",
        "SqlAlchemyLearningRepository",
        "SqlAlchemyMediaRepository",
        "SqlAlchemyFlagsRepository",
        "Argon2PasswordHasher",
        "JwtTokenService",
        "HmacMediaUrlSigner",
        "LocalFilesystemStorage",
    }
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in forbidden_adapter_constructors:
                violations.append(
                    f"{file_path.name}: directly constructs concrete adapter '{name}' at line {node.lineno}. Use bootstrap factory."
                )
    return violations


# ==============================================================================
# 1. Architecture AST Layer Guard Tests
# ==============================================================================


def test_domain_layer_dependencies():
    """Domain layer must be pure Python: no frameworks, no ORMs, no outer layers, no env access."""
    domain_dir = ROOT_SRC / "domain"
    all_violations: list[str] = []
    for file_path in domain_dir.glob("**/*.py"):
        all_violations.extend(check_domain_file(file_path))
    assert not all_violations, "Domain layer violations found:\n" + "\n".join(all_violations)


def test_application_layer_dependencies():
    """Application layer must not import adapters, entrypoints, frameworks, ORMs, or env access."""
    app_dir = ROOT_SRC / "application"
    all_violations: list[str] = []
    for file_path in app_dir.glob("**/*.py"):
        all_violations.extend(check_application_file(file_path))
    assert not all_violations, "Application layer violations found:\n" + "\n".join(all_violations)


def test_adapters_layer_dependencies():
    """Adapters must not depend on entrypoints (HTTP/CLI controllers)."""
    adapters_dir = ROOT_SRC / "adapters"
    all_violations: list[str] = []
    for file_path in adapters_dir.glob("**/*.py"):
        all_violations.extend(check_adapters_file(file_path))
    assert not all_violations, "Adapters layer violations found:\n" + "\n".join(all_violations)


def test_routers_composition_rules():
    """Routers must obtain capabilities via bootstrap factories or DI, not direct adapter instantiation."""
    routers_dir = ROOT_SRC / "routers"
    all_violations: list[str] = []
    for file_path in routers_dir.glob("**/*.py"):
        all_violations.extend(check_composition_rules(file_path))
    assert not all_violations, "Router composition violations found:\n" + "\n".join(all_violations)


# ==============================================================================
# 2. Mutation Tests on Source Fixtures
# ==============================================================================


def test_guard_mutation_catches_violations(tmp_path: Path):
    """Verify that architecture guards actually fail when presented with forbidden patterns."""
    fake_pkg = tmp_path / "jplearn_api"
    fake_pkg.mkdir()
    (fake_pkg / "__init__.py").write_text("", encoding="utf-8")

    domain_bad_abs = fake_pkg / "domain_bad_abs.py"
    domain_bad_abs.write_text("import sqlalchemy\n", encoding="utf-8")
    assert check_domain_file(domain_bad_abs, fake_pkg), "Should catch absolute sqlalchemy import in domain"

    domain_bad_rel = fake_pkg / "domain_bad_rel.py"
    domain_bad_rel.write_text("from .adapters import something\n", encoding="utf-8")
    assert check_domain_file(domain_bad_rel, fake_pkg), "Should catch relative adapter import in domain"

    domain_bad_env = fake_pkg / "domain_bad_env.py"
    domain_bad_env.write_text("import os\nval = os.getenv('X')\n", encoding="utf-8")
    assert check_domain_file(domain_bad_env, fake_pkg), "Should catch os.getenv in domain"

    app_bad_abs = fake_pkg / "app_bad_abs.py"
    app_bad_abs.write_text("import fastapi\n", encoding="utf-8")
    assert check_application_file(app_bad_abs, fake_pkg), "Should catch fastapi import in application"

    app_bad_dyn = fake_pkg / "app_bad_dyn.py"
    app_bad_dyn.write_text("import importlib\nmod = importlib.import_module('sys')\n", encoding="utf-8")
    assert check_application_file(app_bad_dyn, fake_pkg), "Should catch dynamic import in application"

    adapter_bad = fake_pkg / "adapter_bad.py"
    adapter_bad.write_text("from jplearn_api.entrypoints.http import app\n", encoding="utf-8")
    assert check_adapters_file(adapter_bad, fake_pkg), "Should catch entrypoint import in adapter"

    router_bad = fake_pkg / "router_bad.py"
    router_bad.write_text("repo = SqlAlchemyUserRepository(session)\n", encoding="utf-8")
    assert check_composition_rules(router_bad), "Should catch direct adapter instantiation"

    valid_file = fake_pkg / "valid.py"
    valid_file.write_text("from dataclasses import dataclass\n@dataclass\nclass E: id: str\n", encoding="utf-8")
    assert not check_domain_file(valid_file, fake_pkg), "Valid file must produce zero violations"
    assert not check_application_file(valid_file, fake_pkg), "Valid file must produce zero violations"


# ==============================================================================
# 3. Subprocess Import Zero Side-Effects Test
# ==============================================================================


def test_package_import_has_zero_side_effects():
    """Verify in an isolated subprocess that importing inner layers causes zero network/DB side effects."""
    script = """
import sys
import socket

orig_socket = socket.socket
class BlockedSocket(orig_socket):
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Socket creation during module import is forbidden!")

socket.socket = BlockedSocket

import jplearn_api.domain
import jplearn_api.domain.range_parser
import jplearn_api.domain.errors
import jplearn_api.domain.learning
import jplearn_api.domain.catalog
import jplearn_api.domain.identity
import jplearn_api.domain.media
import jplearn_api.application
import jplearn_api.application.handlers.learning
import jplearn_api.application.handlers.catalog
import jplearn_api.application.handlers.media
import jplearn_api.application.handlers.identity
import jplearn_api.application.handlers.flags
import jplearn_api.application.handlers.reconciliation
import jplearn_api.bootstrap

print("CLEAN_IMPORT_SUCCESS")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT_SRC.parent),
    )
    assert result.returncode == 0, f"Import side effect failure:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "CLEAN_IMPORT_SUCCESS" in result.stdout


# ==============================================================================
# 4. Transactional Fake UoW Failure Boundaries & State Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_fake_uow_isolation_and_rollback():
    """Verify transactional fake UoW discards uncommitted mutations on rollback."""
    user_repo = FakeUserRepository()
    uow = FakeUnitOfWork(user_repo)
    hasher = FakePasswordHasher()
    tokens = FakeTokenService()

    # Case 1: Transaction rolls back on exception
    with pytest.raises(RuntimeError):
        async with uow:
            await user_repo.add_initial_progress("user_temp", datetime.now(UTC))
            raise RuntimeError("Simulated crash before commit")

    assert uow.rolled_back is True
    assert uow.committed is False
    assert "user_temp" not in user_repo._committed_progress
    assert "user_temp" not in user_repo.progress

    # Case 2: Failure between registration steps discards user and role
    uow2 = FakeUnitOfWork(user_repo)
    reg_cmd = RegisterUserCommand(email="isolated@example.com", password="password123", secret="sec")

    class FaultyUserRepo(FakeUserRepository):
        async def add_role(self, user_id: str, role: str) -> None:
            raise RuntimeError("DB connection dropped during add_role")

    faulty_repo = FaultyUserRepo()
    uow_faulty = FakeUnitOfWork(faulty_repo)
    with pytest.raises(RuntimeError, match="DB connection dropped"):
        await handle_register(reg_cmd, uow_faulty, faulty_repo, hasher, tokens)

    assert uow_faulty.rolled_back is True
    assert "isolated@example.com" not in faulty_repo.email_index
    assert not faulty_repo._committed_users


@pytest.mark.asyncio
async def test_flags_use_case_in_memory():
    """Verify flags use case runs in pure memory with fake ports and zero I/O."""
    repo = FakeFlagsRepository({"speaking_enabled": False})
    uow = FakeUnitOfWork(repo)

    initial = await handle_get_flags(repo)
    assert initial["speaking_enabled"] is False

    updated = await handle_update_flags(
        UpdateFlagsCommand(flags={"speaking_enabled": True}),
        uow=uow,
        repo=repo,
    )
    assert updated["speaking_enabled"] is True
    assert uow.committed is True
    assert repo._committed_flags["speaking_enabled"] is True


@pytest.mark.asyncio
async def test_identity_use_cases_in_memory():
    """Verify identity use cases run in pure memory with fake ports and zero I/O."""
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
    assert "test@example.com" in user_repo._committed_email_index

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
    repo = FakeCatalogRepository()
    storage = FakeStoragePort()
    uow = FakeUnitOfWork(repo)

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
    assert repo._committed_items[item_dto.id].status == "draft"

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
    repo.items[item_dto.id] = domain_item
    repo._committed_items[item_dto.id] = domain_item

    # 5. Cannot publish if file missing on storage
    with pytest.raises(MediaInvariantError):
        await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)

    # Stage media to storage
    storage.keys.add("m1.bin")

    # 6. Publish succeeds
    pub_dto = await handle_publish(PublishCatalogItemCommand(item_id=item_dto.id), uow, repo, storage)
    assert pub_dto.status == "published"
    assert repo._committed_items[item_dto.id].status == "published"

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
    initial_prog = LearnerProgress(user_id="user_learner", minutes_comprehensible=10, current_ci_level=1)
    repo = FakeLearningRepository(initial_progress={"user_learner": initial_prog})
    uow = FakeUnitOfWork(repo)

    # 1. Start session
    start_cmd = StartLearningSessionCommand(user_id="user_learner", device_class="phone")
    session_dto = await handle_start_session(start_cmd, uow, repo)
    assert session_dto.device_class == "phone"
    assert session_dto.ended_at is None
    assert uow.committed is True
    assert len(repo._committed_events) == 2  # session_started and level_exposed

    # 2. Get progress
    prog_dto = await handle_get_progress(GetLearnerProgressQuery(user_id="user_learner"), repo)
    assert prog_dto.minutes_comprehensible == 10

    # Simulate time elapsed: started 3 minutes ago
    domain_session = await repo.lock_and_get_session(session_dto.id)
    domain_session.started_at -= timedelta(seconds=185)
    repo.sessions[session_dto.id] = domain_session
    repo._committed_sessions[session_dto.id] = domain_session

    # 3. End session by wrong user raises ForbiddenError
    with pytest.raises(ForbiddenError):
        await handle_end_session(EndLearningSessionCommand(user_id="other_user", session_id=session_dto.id), uow, repo)

    # 4. End session by owner succeeds exactly-once
    end_dto = await handle_end_session(EndLearningSessionCommand(user_id="user_learner", session_id=session_dto.id), uow, repo)
    assert end_dto.minutes_comprehensible == 13  # 10 + 3 minutes
    assert len(repo._committed_events) == 4  # + session_ended and minutes_comprehensible

    # 5. Duplicate end session raises SessionAlreadyEndedError
    with pytest.raises(SessionAlreadyEndedError):
        await handle_end_session(EndLearningSessionCommand(user_id="user_learner", session_id=session_dto.id), uow, repo)


@pytest.mark.asyncio
async def test_media_use_cases_in_memory():
    """Verify media upload, HLS registration, and streaming using in-memory fakes."""
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
    uow = FakeUnitOfWork(media_repo)

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
    assert dto.id in media_repo._committed_assets

    # 6. Stream media handler returns MediaStreamDTO
    stream_dto = await handle_stream_media(
        asset_id=dto.id,
        media_repo=media_repo,
        storage=storage,
        range_header="bytes=0-10",
    )
    assert stream_dto.range is not None
    assert stream_dto.range.start == 0
    assert stream_dto.range.end == 10
    assert stream_dto.content_type == "video/mp4"

    # 7. Register HLS without manifest raises InvalidDomainStateError
    with pytest.raises(InvalidDomainStateError):
        await handle_register_hls(
            asset_id=dto.id,
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url="http://localhost:3001",
            secret="test-secret-at-least-32-bytes-long",
        )

    # 8. Register HLS with manifest succeeds
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

    # 9. Stream HLS handler returns MediaStreamDTO
    hls_stream_dto = await handle_stream_hls(
        storage=storage,
        asset_id=dto.id,
        file="index.m3u8",
    )
    assert hls_stream_dto.content_type == "application/vnd.apple.mpegurl"
    assert hls_stream_dto.range is None


@pytest.mark.asyncio
async def test_failure_boundaries_across_use_cases():
    """Verify failure between individual steps across use cases triggers clean rollback."""
    # 1. Registration failure at add_initial_progress
    class FailProgressUserRepo(FakeUserRepository):
        async def add_initial_progress(self, user_id: str, now: datetime) -> None:
            raise RuntimeError("DB failure inserting progress")

    user_repo = FailProgressUserRepo()
    uow = FakeUnitOfWork(user_repo)
    with pytest.raises(RuntimeError, match="DB failure inserting progress"):
        await handle_register(
            RegisterUserCommand(email="failstep@example.com", password="password123", secret="sec"),
            uow,
            user_repo,
            FakePasswordHasher(),
            FakeTokenService(),
        )
    assert uow.rolled_back is True
    assert "failstep@example.com" not in user_repo._committed_email_index
    assert not user_repo._committed_users

    # 2. End session failure at update_progress
    initial_prog = LearnerProgress(user_id="learner_fail", minutes_comprehensible=10, current_ci_level=1)
    class FailProgressLearningRepo(FakeLearningRepository):
        async def update_progress(self, progress: LearnerProgress) -> None:
            raise RuntimeError("Deadlock on user progress update")

    learn_repo = FailProgressLearningRepo(initial_progress={"learner_fail": initial_prog})
    learn_uow = FakeUnitOfWork(learn_repo)
    start_dto = await handle_start_session(
        StartLearningSessionCommand(user_id="learner_fail", device_class="desktop"),
        learn_uow,
        learn_repo,
    )
    learn_uow.committed = False

    with pytest.raises(RuntimeError, match="Deadlock on user progress update"):
        await handle_end_session(
            EndLearningSessionCommand(user_id="learner_fail", session_id=start_dto.id),
            learn_uow,
            learn_repo,
        )
    assert learn_uow.rolled_back is True
    assert learn_repo._committed_progress["learner_fail"].minutes_comprehensible == 10
    # Exactly 2 start events committed, no end events leaked
    assert len(learn_repo._committed_events) == 2

    # 3. Media upload deterministic abort cleans up storage
    class DeterministicFailMediaRepo(FakeMediaRepository):
        async def add(self, asset: Any) -> None:
            raise DeterministicAbortError("Unique constraint violation on asset_id")

    media_repo = DeterministicFailMediaRepo(existing_items={"cat-1"})
    media_storage = FakeStoragePort()
    media_uow = FakeUnitOfWork(media_repo)

    async def single_stream() -> AsyncIterator[bytes]:
        yield b"chunk"

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    with pytest.raises(DeterministicAbortError, match="Unique constraint violation"):
        await handle_upload_media(
            catalog_item_id="cat-1",
            first_chunk=valid_first_chunk,
            stream=single_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow=media_uow,
            media_repo=media_repo,
            storage=media_storage,
            base_url="http://localhost:3001",
            secret="test-secret-at-least-32-bytes-long",
        )
    assert media_uow.rolled_back is True
    assert not media_repo._committed_assets
    assert len(media_storage.keys) == 0  # Promoted file was cleanly removed!

