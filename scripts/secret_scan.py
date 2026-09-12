#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{36,}\b'),
    'aws access key': re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),
    'slack token': re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b'),
    'stripe live secret': re.compile(r'\bsk_live_[A-Za-z0-9]{16,}\b'),
    'openai secret': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b'),
}

SKIP_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.woff', '.woff2'}
SKIP_PATHS = {'scripts/secret_scan.py'}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(['git', 'ls-files', '-z'])
    return [Path(item.decode()) for item in output.split(b'\0') if item]


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in tracked_files():
        if str(path) in SKIP_PATHS or path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((str(path), line_number, name))
    if findings:
        print('High-confidence secret material detected in tracked files:')
        for path, line, kind in findings:
            print(f'  {path}:{line}: {kind}')
        return 1
    print('Secret scan passed: no high-confidence credential material found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
