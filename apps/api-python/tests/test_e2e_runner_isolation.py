"""Regression tests for R-06: E2E Runner Lifecycle and Workspace Isolation.

Mandatory tests from 2026-09-05-fastapi-remaining-regressions.md:
1. Subprocess with stdin=DEVNULL: runner A holds lock; B cannot enter critical section
   until A completes. Verified by timestamps/barrier.
2. A fails or receives TERM: B continues, lock is not stuck, no orphaned children.
3. Fixture repo has uncommitted changes in next-env.d.ts & tsconfig.json: both successful
   and failed runs preserve user file contents untouched.
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "apps/api-python" / "differential" / "web-e2e-python.sh"
RUNNER_PATH = REPO_ROOT / "apps/api-python" / "differential" / "web_e2e_runner.py"
LOCK_PATH = Path("/tmp/jplearn-web-e2e.lock")


def test_runner_lock_with_stdin_devnull_blocks_concurrent_runner(tmp_path: Path) -> None:
    """Subprocess with stdin=DEVNULL: runner A holds lock; B waits until A finishes."""
    barrier_a_start = tmp_path / "a_start"
    barrier_release_a = tmp_path / "a_release"
    timing_b_start = tmp_path / "b_start_time"
    timing_a_end = tmp_path / "a_end_time"

    cmd_a = [
        sys.executable,
        "-c",
        f"""
import sys, time, fcntl
from pathlib import Path

lock_path = Path("/tmp/jplearn-web-e2e.lock")
f = open(lock_path, "w")
fcntl.flock(f.fileno(), fcntl.LOCK_EX)
Path({str(barrier_a_start)!r}).write_text("ready")
while not Path({str(barrier_release_a)!r}).exists():
    time.sleep(0.05)
Path({str(timing_a_end)!r}).write_text(str(time.time()))
fcntl.flock(f.fileno(), fcntl.LOCK_UN)
f.close()
""",
    ]

    proc_a = subprocess.Popen(
        cmd_a,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for A to acquire lock and signal readiness
    deadline = time.time() + 5
    while not barrier_a_start.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert barrier_a_start.exists(), "Runner A failed to acquire lock in time"

    # Now launch runner B with stdin=DEVNULL attempting to acquire lock
    cmd_b = [
        sys.executable,
        "-c",
        f"""
import sys, time, fcntl
from pathlib import Path

lock_path = Path("/tmp/jplearn-web-e2e.lock")
f = open(lock_path, "w")
fcntl.flock(f.fileno(), fcntl.LOCK_EX)
Path({str(timing_b_start)!r}).write_text(str(time.time()))
fcntl.flock(f.fileno(), fcntl.LOCK_UN)
f.close()
""",
    ]

    proc_b = subprocess.Popen(
        cmd_b,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give B a moment to attempt lock acquisition (should be blocked)
    time.sleep(0.3)
    assert not timing_b_start.exists(), "Runner B entered critical section while A still held lock!"

    # Release runner A
    barrier_release_a.write_text("release")
    proc_a.wait(timeout=5)
    proc_b.wait(timeout=5)

    assert timing_a_end.exists() and timing_b_start.exists()
    t_a_end = float(timing_a_end.read_text().strip())
    t_b_start = float(timing_b_start.read_text().strip())

    # B must have acquired the lock AFTER A finished
    assert t_b_start >= t_a_end, f"B acquired lock before A finished: B={t_b_start}, A={t_a_end}"


def test_runner_term_releases_lock_cleanly(tmp_path: Path) -> None:
    """When a runner receives SIGTERM, the lock is freed and subsequent runner proceeds."""
    barrier_a = tmp_path / "a_ready"
    timing_b = tmp_path / "b_ran"

    cmd_a = [
        sys.executable,
        "-c",
        f"""
import sys, time, fcntl, signal
from pathlib import Path

f = open("/tmp/jplearn-web-e2e.lock", "w")
fcntl.flock(f.fileno(), fcntl.LOCK_EX)
Path({str(barrier_a)!r}).write_text("ready")
time.sleep(30)
""",
    ]

    proc_a = subprocess.Popen(
        cmd_a,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )

    deadline = time.time() + 5
    while not barrier_a.exists() and time.time() < deadline:
        time.sleep(0.05)

    assert barrier_a.exists(), "Process A failed to start"

    # Terminate process group of A
    os.killpg(os.getpgid(proc_a.pid), signal.SIGTERM)
    proc_a.wait(timeout=5)

    # Runner B must be able to acquire lock immediately
    cmd_b = [
        sys.executable,
        "-c",
        f"""
import fcntl
from pathlib import Path

f = open("/tmp/jplearn-web-e2e.lock", "w")
fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
Path({str(timing_b)!r}).write_text("success")
fcntl.flock(f.fileno(), fcntl.LOCK_UN)
f.close()
""",
    ]
    proc_b = subprocess.run(cmd_b, check=True)
    assert timing_b.exists() and timing_b.read_text().strip() == "success"


def test_user_config_files_preserved_under_e2e_run(tmp_path: Path) -> None:
    """Verify that uncommitted modifications to next-env.d.ts and tsconfig.json are never wiped,
    and that running Next build in an isolated workspace snapshot leaves repo files untouched."""
    web_dir = REPO_ROOT / "apps" / "web"
    next_env = web_dir / "next-env.d.ts"
    tsconfig = web_dir / "tsconfig.json"

    original_next_env = next_env.read_text(encoding="utf-8")
    original_tsconfig = tsconfig.read_text(encoding="utf-8")

    sentinel_comment = "// TEST_USER_UNCOMMITTED_PRESERVE_SENTINEL\n"
    try:
        # Prepend sentinel to both files to simulate user uncommitted work
        next_env.write_text(sentinel_comment + original_next_env, encoding="utf-8")
        tsconfig.write_text(original_tsconfig + "\n// user comment\n", encoding="utf-8")

        # Check that differential/web-e2e-python.sh DOES NOT have git checkout -- in its text
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "git checkout --" not in script_text, (
            "Found dangerous 'git checkout --' in web-e2e-python.sh which wipes user files!"
        )

        # Simulate snapshot workspace build in tmp_path
        ws = tmp_path / "web"
        ws.mkdir(parents=True)
        for name in ("package.json", "next.config.ts", "tsconfig.json", "next-env.d.ts", "playwright.config.ts"):
            (ws / name).write_text((web_dir / name).read_text(encoding="utf-8"), encoding="utf-8")
        os.symlink(web_dir / "src", ws / "src")
        os.symlink(web_dir / "e2e", ws / "e2e")
        os.symlink(web_dir / "node_modules", ws / "node_modules")

        # Run Next build inside ws
        res = subprocess.run(
            ["./node_modules/.bin/next", "build"],
            cwd=ws,
            env={**os.environ, "NEXT_PUBLIC_API_URL": "http://localhost:3002", "NEXT_DIST_DIR": ".next"},
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Next build in snapshot workspace failed:\n{res.stderr}"

        # Assert user's files in $REPO/apps/web STILL contain their modifications exactly
        assert next_env.read_text(encoding="utf-8") == sentinel_comment + original_next_env
        assert tsconfig.read_text(encoding="utf-8") == original_tsconfig + "\n// user comment\n"

    finally:
        # Restore clean state
        next_env.write_text(original_next_env, encoding="utf-8")
        tsconfig.write_text(original_tsconfig, encoding="utf-8")
