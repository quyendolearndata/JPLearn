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
