#!/usr/bin/env python3
"""Read-only negative HTTP probes. Explicit staging opt-in, no real data.

Only exercises unauthenticated calls. Never sends passwords or personal data.
Expected: 401/403 (optionally 404 for concealed routes) on protected endpoints.
"""
import argparse, json, ssl, sys, urllib.error, urllib.parse, urllib.request

PATHS = [
    ('GET', '/api/v1/local-signatures/me/status', None),
    ('POST', '/api/v1/local-signatures/clients/lookup', {'national_id': 'SYNTHETIC-NOT-A-CLIENT'}),
    ('POST', '/api/v1/local-signatures/captures', {'signer_kind':'operator'}),
    ('POST', '/api/v1/wacom-bridge/device-challenges', {'workstation_id':'00000000-0000-4000-8000-000000000000'}),
    ('POST', '/api/v1/wacom-bridge/sessions/revoke', None),
]


def main():
    p=argparse.ArgumentParser(description='Uncredentialed Wacom staging denial probes')
    p.add_argument('--origin', required=True)
    p.add_argument('--confirm-staging-only', action='store_true')
    a=p.parse_args()
    u=urllib.parse.urlparse(a.origin)
    if not a.confirm_staging_only or u.scheme!='https' or not u.hostname or u.path not in ('','/') or u.query or u.fragment:
        sys.exit('Refusing: --confirm-staging-only and a bare HTTPS staging origin required')
    if any(x in u.hostname.lower() for x in ('localhost','127.0.0.1','prod')):
        sys.exit('Refusing: invalid staging target')
    if not any(x in u.hostname.lower() for x in ('stage','staging','test')):
        sys.exit('Refusing: hostname must explicitly indicate staging/test')
    failed=False
    for method,path,payload in PATHS:
        req=urllib.request.Request(a.origin.rstrip('/')+path,method=method,
          headers={'Accept':'application/json','Cache-Control':'no-store',
                   'Content-Type':'application/json'},
          data=json.dumps(payload or {}).encode() if method=='POST' else None)
        try:
            with urllib.request.urlopen(req,timeout=8) as response:
                status=response.status
        except urllib.error.HTTPError as e:
            status=e.code
        except Exception as e:
            print(f'INCONCLUSIVE {method} {path}: {type(e).__name__}')
            failed=True
            continue
        ok=status in (401,403,404)
        print(f'{"PASS" if ok else "FAIL"} {method} {path}: HTTP {status}')
        if not ok: failed=True
    if failed: sys.exit(1)
    print('Unauthenticated negative probes passed. Does NOT prove authorized workstation workflow.')

if __name__=='__main__': main()
