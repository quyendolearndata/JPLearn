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
        except Exception as start_err:
            print(f"Failed to launch supervised command {cmd}: {start_err}", file=sys.stderr)
            return 1

        signalled: list[int | None] = [None]

        def handle_signal(signum, frame):
            signalled[0] = int(signum)
            try:
                pgid = os.getpgid(child.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # Monitor child and handle graceful termination / escalation if signalled
        while child.poll() is None:
            if signalled[0] is not None:
                # Wait up to 5.0 seconds for child group to terminate under SIGTERM
                deadline = time.time() + 5.0
                while child.poll() is None and time.time() < deadline:
                    time.sleep(0.05)
                # Escalate to SIGKILL if child is still alive
                if child.poll() is None:
                    try:
                        pgid = os.getpgid(child.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                    deadline_kill = time.time() + 2.0
                    while child.poll() is None and time.time() < deadline_kill:
                        time.sleep(0.05)
                return 128 + signalled[0]
            time.sleep(0.05)

        if signalled[0] is not None:
            return 128 + signalled[0]

        return child.returncode
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()


if __name__ == "__main__":
    sys.exit(main())
