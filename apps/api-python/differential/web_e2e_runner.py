#!/usr/bin/env python3
"""Supervisor runner for differential/web-e2e-python.sh (R-06).

Owns the lock file descriptor flock throughout the entire lifecycle of the E2E run
and its child cleanup, independently of stdin/terminal availability.
"""

from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

LOCK_PATH = Path(os.environ.get("JPLEARN_E2E_LOCK_PATH", "/tmp/jplearn-web-e2e.lock"))
TERM_GRACE_SECONDS = float(os.environ.get("JPLEARN_E2E_TERM_GRACE_SECONDS", "5.0"))
KILL_GRACE_SECONDS = float(os.environ.get("JPLEARN_E2E_KILL_GRACE_SECONDS", "2.0"))


def acquire_flock(lock_fd: int) -> None:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            print(
                f"[{timestamp}] == Another E2E run is in progress. Waiting for lock... ==",
                flush=True,
            )
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        else:
            raise


def process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_process_group_exit(child: subprocess.Popen, pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while process_group_exists(pgid) and time.monotonic() < deadline:
        child.poll()  # reap the direct child as soon as it exits
        time.sleep(0.05)
    child.poll()
    return not process_group_exists(pgid)


def terminate_process_group(
    child: subprocess.Popen,
    pgid: int,
    *,
    term_already_sent: bool = False,
) -> bool:
    if not term_already_sent and process_group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return True

    if wait_for_process_group_exit(child, pgid, TERM_GRACE_SECONDS):
        return True

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return wait_for_process_group_exit(child, pgid, KILL_GRACE_SECONDS)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    # Support testing seam: arguments after '--' specify custom child command
    if "--" in args:
        idx = args.index("--")
        cmd = args[idx + 1 :]
        if not cmd:
            print("Error: '--' specified without a command", file=sys.stderr)
            return 2
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        script_path = repo_root / "apps" / "api-python" / "differential" / "web-e2e-python.sh"
        cmd = ["bash", str(script_path)] + args

    # Open lock file; descriptor remains held in this supervisor process
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(LOCK_PATH, "w")
    acquire_flock(lock_file.fileno())

    try:
        env = os.environ.copy()
        env["JPLEARN_E2E_SUPERVISED"] = "1"

        try:
            # Run child in a new process group so we can forward signals cleanly
            child = subprocess.Popen(
                cmd,
                env=env,
                preexec_fn=os.setsid,
            )
            child_pgid = child.pid
        except Exception as start_err:
            print(f"Failed to launch supervised command {cmd}: {start_err}", file=sys.stderr)
            return 1

        signalled: list[int | None] = [None]

        def handle_signal(signum, frame):
            signalled[0] = int(signum)
            try:
                os.killpg(child_pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # Monitor the direct child, but keep ownership of its entire process
        # group until every descendant has exited.
        while child.poll() is None and signalled[0] is None:
            time.sleep(0.05)

        if signalled[0] is not None:
            cleaned = terminate_process_group(
                child,
                child_pgid,
                term_already_sent=True,
            )
            if not cleaned:
                print(
                    f"Failed to terminate child process group {child_pgid}",
                    file=sys.stderr,
                )
            return 128 + signalled[0]

        returncode = child.returncode
        if process_group_exists(child_pgid):
            cleaned = terminate_process_group(child, child_pgid)
            if not cleaned:
                print(
                    f"Failed to terminate orphaned child process group {child_pgid}",
                    file=sys.stderr,
                )
                return 1
        return returncode
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()


if __name__ == "__main__":
    sys.exit(main())
