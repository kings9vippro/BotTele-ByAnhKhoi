"""Fail CI when common high-impact credentials are committed.

This is intentionally a small, deterministic guard rather than a replacement
for a full secret-scanning service.  It reports only file and line metadata;
matched values are never printed to CI logs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Telegram bot tokens have a stable public shape.  Keep this specific so test
# values such as ``ci-test-token`` remain valid and useful in CI.
TELEGRAM_TOKEN = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [ROOT / name for name in result.stdout.decode("utf-8").split("\0") if name]


def scan_file(path: Path) -> list[tuple[int, str]]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if b"\0" in data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if TELEGRAM_TOKEN.search(line):
            findings.append((line_number, "telegram bot token"))
        if PRIVATE_KEY.search(line):
            findings.append((line_number, "private key"))
    return findings


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for path in tracked_files():
        for line_number, kind in scan_file(path):
            findings.append((path, line_number, kind))

    if findings:
        print("Potential committed credentials detected:", file=sys.stderr)
        for path, line_number, kind in findings:
            # Do not print the matched line: CI logs are retained and public
            # logs would turn a finding into an additional disclosure.
            print(f"- {path.relative_to(ROOT)}:{line_number} ({kind})", file=sys.stderr)
        return 1

    print("Secret scan passed: no Telegram bot token or private key in tracked files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Secret scan could not enumerate tracked files: {error}", file=sys.stderr)
        raise SystemExit(2) from error
