#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a command and prefix stdout/stderr lines with Asia/Shanghai time."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


child: subprocess.Popen[str] | None = None


def _timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("LOG_TZ") or os.getenv("TZ") or "Asia/Shanghai")


def timestamp() -> str:
    return datetime.now(_timezone()).strftime("%Y-%m-%d %H:%M:%S %Z")


def forward_signal(signum: int, _frame) -> None:
    if child and child.poll() is None:
        child.send_signal(signum)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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

    assert child.stdout is not None
    for line in child.stdout:
        print(f"[{timestamp()}] {line}", end="", flush=True)

    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
