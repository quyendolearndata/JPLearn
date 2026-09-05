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

LOCK_PATH = Path("/tmp/jplearn-web-e2e.lock")


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


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    script_path = repo_root / "apps" / "api-python" / "differential" / "web-e2e-python.sh"

    # Open lock file; descriptor remains held in this supervisor process
    lock_file = open(LOCK_PATH, "w")
    acquire_flock(lock_file.fileno())

    try:
        env = os.environ.copy()
        env["JPLEARN_E2E_SUPERVISED"] = "1"

        cmd = ["bash", str(script_path)] + sys.argv[1:]

        # Run child in a new process group so we can forward signals cleanly
        child = subprocess.Popen(
            cmd,
            env=env,
            preexec_fn=os.setsid,
        )

        def handle_signal(signum, frame):
            try:
                pgid = os.getpgid(child.pid)
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        exit_code = child.wait()
        return exit_code
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()


if __name__ == "__main__":
    sys.exit(main())
