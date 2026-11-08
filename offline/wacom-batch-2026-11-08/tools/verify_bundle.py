#!/usr/bin/env python3
from __future__ import annotations
import ast, hashlib, pathlib, subprocess, sys, zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
files=list((ROOT/'payload').rglob('*'))
assert sum(x.is_file() for x in files)>=8, 'Missing source modules'
for p in files:
    if p.suffix == '.py':
        ast.parse(p.read_text(),filename=str(p))
for path in (ROOT/'payload').rglob('*'):
    if path.is_file() and path.stat().st_size == 0:
        raise RuntimeError(f'Empty source: {path}')
print('PASS Python syntax and source bundle inventory')
for path in sorted(p for p in files if p.is_file()):
    print(hashlib.sha256(path.read_bytes()).hexdigest(),path.relative_to(ROOT))
