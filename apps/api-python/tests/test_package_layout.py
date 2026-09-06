"""Public launch paths and resource lookup survive package relocation."""

import os
from pathlib import Path
import subprocess
import sys
import tomllib

from jplearn_api.entrypoints.cli.migrate import MIGRATIONS_DIR, alembic_config, load_baseline_schema
from jplearn_api.tooling.openapi_diff import handwritten_spec_path


def test_resources_and_contract_resolve_outside_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCHEMA_BASELINE_PATH", raising=False)
    monkeypatch.delenv("OPENAPI_SPEC_PATH", raising=False)
    assert (MIGRATIONS_DIR / "env.py").is_file()
    assert (MIGRATIONS_DIR / "versions" / "0001_prisma_baseline.py").is_file()
    assert len(load_baseline_schema("0001_prisma_baseline")["tables"]) == 10
    assert len(load_baseline_schema("head")["tables"]) == 11
    assert handwritten_spec_path().is_file()
    config = alembic_config("postgresql://test:test@localhost/jplearn_test")
    assert Path(config.get_main_option("script_location")) == MIGRATIONS_DIR


def test_console_entrypoints_target_canonical_modules():
    api_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((api_root / "pyproject.toml").read_text())
    assert project["project"]["scripts"] == {
        "jplearn-migrate": "jplearn_api.entrypoints.cli.migrate:main",
        "jplearn-seed": "jplearn_api.entrypoints.cli.seed:main",
        "jplearn-openapi-diff": "jplearn_api.tooling.openapi_diff:main",
    }


def test_migration_module_help_without_configuration(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in {
        "DATABASE_URL", "JWT_SECRET", "ENVIRONMENT", "SCHEMA_BASELINE_PATH",
    }}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-m", "jplearn_api.entrypoints.cli.migrate", "--help"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "jplearn-migrate" in result.stdout
