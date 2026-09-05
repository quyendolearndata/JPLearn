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
