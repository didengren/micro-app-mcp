#!/usr/bin/env python3
"""Detect whether pyproject version changed in staged changes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Sequence

VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.M)


def run_git(args: Sequence[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return proc.stdout


def extract_version(pyproject_text: str) -> str:
    match = VERSION_RE.search(pyproject_text)
    if match is None:
        raise ValueError("failed to parse version from pyproject.toml")
    return match.group(1)


def read_staged_pyproject() -> str:
    return run_git(["show", ":pyproject.toml"])


def read_head_pyproject() -> str:
    return run_git(["show", "HEAD:pyproject.toml"])


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-version", action="store_true", help="print staged version")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        staged_text = read_staged_pyproject()
    except Exception as exc:
        print(f"error: cannot read staged pyproject.toml: {exc}", file=sys.stderr)
        return 1

    try:
        staged_version = extract_version(staged_text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.new_version:
        print(staged_version)
        return 0

    head_version = ""
    try:
        head_text = read_head_pyproject()
        head_version = extract_version(head_text)
    except Exception:
        # 初始提交或文件不存在时，认为发生了版本变化
        head_version = ""

    print("changed" if staged_version != head_version else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
