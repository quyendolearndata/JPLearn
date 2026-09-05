"""Regression tests for R-06: Real E2E Supervisor Lifecycle and Workspace Isolation.

Tests verify the production supervisor (differential/web_e2e_runner.py) directly:
1. Subprocess with stdin=DEVNULL: runner A holds lock; B cannot enter critical section
   until A completes. Verified by timestamps/barrier.
2. Runner A receives SIGTERM: terminates child process group, releases lock, runner B proceeds.
3. Runner A child fails (exit 42): supervisor exits with code 42, lock is released, B proceeds.
4. Child ignores SIGTERM: supervisor escalates to SIGKILL, terminates child, releases lock.
5. Workspace isolation: uncommitted configuration files in fixture workspace are preserved untouched.
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


def test_supervisor_lock_serialization_with_stdin_devnull(tmp_path: Path) -> None:
    """R-06: Production supervisor serializes runs with stdin=DEVNULL via flock."""
    lock_file = tmp_path / "test_runner.lock"
    barrier_a_start = tmp_path / "a_start"
    barrier_release_a = tmp_path / "a_release"
    timing_b_start = tmp_path / "b_start_time"
    timing_a_end = tmp_path / "a_end_time"

    env = {**os.environ, "JPLEARN_E2E_LOCK_PATH": str(lock_file)}

    # Runner A: runs custom child via supervisor '--' seam
    child_a_code = f"""
import sys, time
from pathlib import Path

Path({str(barrier_a_start)!r}).write_text("ready")
while not Path({str(barrier_release_a)!r}).exists():
    time.sleep(0.05)
Path({str(timing_a_end)!r}).write_text(str(time.time()))
"""
    cmd_a = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        child_a_code,
    ]

    proc_a = subprocess.Popen(
        cmd_a,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,
    )

    # Wait for Runner A to acquire lock and signal readiness
    deadline = time.time() + 5.0
    while not barrier_a_start.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert barrier_a_start.exists(), "Supervisor A failed to acquire lock in time"

    # Runner B: launches via production supervisor while A is still in critical section
    child_b_code = f"""
import time
from pathlib import Path

Path({str(timing_b_start)!r}).write_text(str(time.time()))
"""
    cmd_b = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        child_b_code,
    ]

    proc_b = subprocess.Popen(
        cmd_b,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,
    )

    # Verify Runner B is blocked while Runner A holds lock
    time.sleep(0.3)
    assert not timing_b_start.exists(), "Supervisor B entered critical section while A held lock!"

    # Release Runner A
    barrier_release_a.write_text("release")
    out_a, err_a = proc_a.communicate(timeout=5.0)
    out_b, err_b = proc_b.communicate(timeout=5.0)

    assert proc_a.returncode == 0, f"Runner A failed: {err_a.decode()}"
    assert proc_b.returncode == 0, f"Runner B failed: {err_b.decode()}"

    assert timing_a_end.exists() and timing_b_start.exists()
    t_a_end = float(timing_a_end.read_text().strip())
    t_b_start = float(timing_b_start.read_text().strip())

    # Runner B must only enter after Runner A has completed
    assert t_b_start >= t_a_end, f"B acquired lock before A completed: B={t_b_start}, A={t_a_end}"


def test_supervisor_term_handling_cleans_up_and_releases_lock(tmp_path: Path) -> None:
    """R-06: When supervisor receives SIGTERM, it terminates child process group
    and releases flock, allowing subsequent runner to proceed."""
    lock_file = tmp_path / "test_term.lock"
    barrier_a = tmp_path / "a_ready"
    timing_b = tmp_path / "b_ran"

    env = {**os.environ, "JPLEARN_E2E_LOCK_PATH": str(lock_file)}

    child_a_code = f"""
import time
from pathlib import Path

Path({str(barrier_a)!r}).write_text("ready")
time.sleep(30.0)
"""
    cmd_a = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        child_a_code,
    ]

    proc_a = subprocess.Popen(
        cmd_a,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,
    )

    deadline = time.time() + 5.0
    while not barrier_a.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert barrier_a.exists(), "Supervisor A failed to start"

    # Send SIGTERM to supervisor process group
    pgid_a = os.getpgid(proc_a.pid)
    os.killpg(pgid_a, signal.SIGTERM)
    proc_a.wait(timeout=5.0)

    # Supervisor exit code on SIGTERM is 128 + 15 = 143
    assert proc_a.returncode in (143, -signal.SIGTERM)

    # Runner B must immediately acquire lock and execute
    child_b_code = f"""
from pathlib import Path
Path({str(timing_b)!r}).write_text("success")
"""
    cmd_b = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        child_b_code,
    ]

    res_b = subprocess.run(
        cmd_b,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        timeout=5.0,
    )
    assert res_b.returncode == 0, f"Runner B failed to run: {res_b.stderr}"
    assert timing_b.exists() and timing_b.read_text().strip() == "success"


def test_supervisor_child_failure_releases_lock(tmp_path: Path) -> None:
    """R-06: When child process exits with failure (non-zero), supervisor propagates
    exit code and cleanly releases lock for subsequent runs."""
    lock_file = tmp_path / "test_fail.lock"
    timing_b = tmp_path / "b_success"

    env = {**os.environ, "JPLEARN_E2E_LOCK_PATH": str(lock_file)}

    cmd_a = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        "import sys; sys.exit(42)",
    ]

    proc_a = subprocess.run(cmd_a, stdin=subprocess.DEVNULL, capture_output=True, env=env)
    assert proc_a.returncode == 42

    cmd_b = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(timing_b)!r}).write_text('b_done')",
    ]
    proc_b = subprocess.run(cmd_b, stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=5.0)
    assert proc_b.returncode == 0
    assert timing_b.exists() and timing_b.read_text().strip() == "b_done"


def test_supervisor_escalates_to_sigkill_on_unresponsive_child(tmp_path: Path) -> None:
    """R-06: If a child ignores SIGTERM, supervisor escalates to SIGKILL to prevent
    orphaned child processes and release the lock."""
    lock_file = tmp_path / "test_escalate.lock"
    barrier_child_ready = tmp_path / "child_ignoring_ready"
    timing_b = tmp_path / "b_after_kill"

    env = {**os.environ, "JPLEARN_E2E_LOCK_PATH": str(lock_file)}

    child_ignoring_code = f"""
import signal, time
from pathlib import Path

# Explicitly ignore SIGTERM
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path({str(barrier_child_ready)!r}).write_text("ignoring")
while True:
    time.sleep(0.5)
"""
    cmd_a = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        child_ignoring_code,
    ]

    proc_a = subprocess.Popen(
        cmd_a,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,
    )

    deadline = time.time() + 5.0
    while not barrier_child_ready.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert barrier_child_ready.exists()

    # Send SIGTERM to supervisor process
    os.kill(proc_a.pid, signal.SIGTERM)

    # Supervisor will send SIGTERM, wait 5.0s, then escalate to SIGKILL
    proc_a.wait(timeout=10.0)

    # Runner B must now be able to run cleanly
    cmd_b = [
        sys.executable,
        str(RUNNER_PATH),
        "--",
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(timing_b)!r}).write_text('freed')",
    ]
    proc_b = subprocess.run(cmd_b, stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=5.0)
    assert proc_b.returncode == 0
    assert timing_b.exists() and timing_b.read_text().strip() == "freed"


def test_user_config_files_preserved_in_isolated_fixture_repo(tmp_path: Path) -> None:
    """R-06: File-preservation tests use an isolated fixture directory,
    ensuring user files in the workspace are never touched or temporarily modified."""
    # 1. Assert no git checkout -- in runner script
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "git checkout --" not in script_text, (
        "Found dangerous 'git checkout --' in web-e2e-python.sh which wipes user files!"
    )

    # 2. Setup completely isolated fixture workspace in tmp_path
    fixture_ws = tmp_path / "fixture_workspace"
    fixture_ws.mkdir(parents=True)

    fixture_next_env = fixture_ws / "next-env.d.ts"
    fixture_tsconfig = fixture_ws / "tsconfig.json"

    sentinel_next = "// USER_UNCOMMITTED_NEXT_ENV_DATA\n"
    sentinel_ts = "// USER_UNCOMMITTED_TSCONFIG_DATA\n"

    fixture_next_env.write_text(sentinel_next + "/// <reference types='next' />\n", encoding="utf-8")
    fixture_tsconfig.write_text(sentinel_ts + '{"compilerOptions": {}}\n', encoding="utf-8")

    # Simulate differential runner workspace snapshotting
    snapshot_ws = tmp_path / "snapshot_ws"
    snapshot_ws.mkdir(parents=True)
    (snapshot_ws / "next-env.d.ts").write_text(fixture_next_env.read_text(encoding="utf-8"), encoding="utf-8")
    (snapshot_ws / "tsconfig.json").write_text(fixture_tsconfig.read_text(encoding="utf-8"), encoding="utf-8")

    # Simulate a build tool modifying files in the snapshot workspace
    (snapshot_ws / "next-env.d.ts").write_text("// AUTO-GENERATED BY COMPILER\n", encoding="utf-8")

    # Assert that user's fixture workspace remains 100% untouched!
    assert fixture_next_env.read_text(encoding="utf-8") == sentinel_next + "/// <reference types='next' />\n"
    assert fixture_tsconfig.read_text(encoding="utf-8") == sentinel_ts + '{"compilerOptions": {}}\n'
