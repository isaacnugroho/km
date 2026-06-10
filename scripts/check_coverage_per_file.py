#!/usr/bin/env python3
"""Fail when any src/km module falls below a per-file coverage threshold."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_LINE = re.compile(
    r"^(?P<path>src/km/\S+)\s+\d+\s+\d+\s+(?P<pct>\d+)%"
)


def collect_below_threshold(min_pct: int) -> list[tuple[str, int]]:
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "report", "--include=src/km/*"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "coverage report failed")

    below: list[tuple[str, int]] = []
    for line in result.stdout.splitlines():
        match = COVERAGE_LINE.match(line.strip())
        if match and int(match.group("pct")) < min_pct:
            below.append((match.group("path"), int(match.group("pct"))))
    return sorted(below, key=lambda item: item[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min",
        type=int,
        default=80,
        help="Minimum required coverage percentage per file (default: 80)",
    )
    args = parser.parse_args(argv)

    below = collect_below_threshold(args.min)
    if below:
        print(f"Per-file coverage below {args.min}%:", file=sys.stderr)
        for path, pct in below:
            print(f"  {path}: {pct}%", file=sys.stderr)
        return 1

    print(f"All src/km modules meet the {args.min}% per-file coverage threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
