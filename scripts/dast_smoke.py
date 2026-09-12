#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time

import requests


BASE_URL = os.environ.get('LOANHUB_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    session = requests.Session()
    ready = None
    for _ in range(40):
        try:
            ready = session.get(f'{BASE_URL}/health/ready', timeout=2)
            if ready.status_code in {200, 503}:
                break
        except requests.RequestException:
            pass
        time.sleep(0.5)
    require(ready is not None and ready.status_code == 200, 'API readiness check did not become healthy')

    protected = session.get(f'{BASE_URL}/api/v1/auth/me', timeout=3)
    require(protected.status_code in {401, 403}, 'Unauthenticated auth/me request was not rejected')
    require('traceback' not in protected.text.lower(), 'Technical traceback leaked to unauthenticated client')
    require(protected.headers.get('X-Content-Type-Options') == 'nosniff', 'Missing nosniff security header')
    require(protected.headers.get('X-Frame-Options') == 'DENY', 'Missing anti-framing security header')

    traversal = session.get(f'{BASE_URL}/api/v1/files/../../etc/passwd', timeout=3)
    require(traversal.status_code in {400, 401, 403, 404}, 'Traversal probe was not safely rejected')
    require('traceback' not in traversal.text.lower(), 'Traversal probe leaked a traceback')

    throttled = False
    for _ in range(12):
        response = session.post(
            f'{BASE_URL}/api/v1/auth/login',
            json={'phone': '59999999', 'password': 'invalid-ci-password'},
            timeout=3,
        )
        if response.status_code == 429:
            throttled = True
            require(int(response.headers.get('Retry-After', '0')) > 0, '429 response missing Retry-After')
            break
        require(response.status_code in {401, 422}, f'Unexpected login-probe status {response.status_code}')
    require(throttled, 'Authentication rate limit did not activate')

    print('Automated DAST baseline passed: authz, error leakage, traversal, headers and rate limiting.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, requests.RequestException) as error:
        print(f'DAST baseline FAILED: {error}', file=sys.stderr)
        raise SystemExit(1)
