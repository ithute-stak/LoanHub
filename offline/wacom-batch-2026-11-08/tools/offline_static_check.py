#!/usr/bin/env python3
"""Syntax + best-effort premerge offline checks, no remote access."""
import argparse, pathlib, py_compile, subprocess, sys

p=argparse.ArgumentParser()
p.add_argument('--repo', type=pathlib.Path,required=True)
a=p.parse_args()
repo=a.repo.resolve()
paths=[
 'apps/backend/routers/wacom_bridge_device_proof.py',
 'apps/backend/services/wacom_bridge_sessions.py',
 'apps/backend/tests/test_wacom_offline_admission_contract.py',
]
for rel in paths:
    f=repo/rel
    if not f.is_file():sys.exit(f'Missing: {f}')
    py_compile.compile(str(f),doraise=True)
    print('PY SYNTAX OK',rel)
worker=repo/'services/wacom-connector'
for cmd in [['gofmt','-d','loanhub_offline_session_security_test.go'], ['go','test','./...']]:
    print('RUN',cmd)
    try:
        r=subprocess.run(cmd,cwd=worker,check=False,timeout=180)
    except (FileNotFoundError,subprocess.TimeoutExpired) as exc:
        sys.exit(f'Tool unavailable or timeout: {exc}')
    if r.returncode:sys.exit(f'Offline verification failed: {cmd}')
print('Static and Go tests passed; run PostgreSQL-backed FastAPI suite before merge.')
