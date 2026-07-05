#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a command and prefix each output line with local date/time."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path


child: subprocess.Popen[str] | None = None


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def forward_signal(signum: int, _frame) -> None:
    if child and child.poll() is None:
        child.send_signal(signum)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, help="Path to the log file to write.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --.")
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing command")
    return args


def main() -> int:
    global child
    args = parse_args()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    child = subprocess.Popen(
        args.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
        assert child.stdout is not None
        for line in child.stdout:
            log_file.write(f"[{timestamp()}] {line}")

    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
