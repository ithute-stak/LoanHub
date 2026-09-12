from __future__ import annotations

import os

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect, sync_playwright


WEB = os.getenv('LOANHUB_WEB_BASE_URL')
API = os.getenv('LOANHUB_API_BASE_URL')
PHONE = os.getenv('LOANHUB_E2E_PHONE')
PASSWORD = os.getenv('LOANHUB_E2E_PASSWORD')

pytestmark = pytest.mark.skipif(
    not all([WEB, API, PHONE, PASSWORD]),
    reason='browser E2E environment is not configured',
)


def test_real_browser_login_and_lending_workflow_contract():
    """Exercise login, responsive app chrome and the live lending API contract.

    Detailed financial transition invariants remain covered by backend regression
    tests; this browser gate catches broken browser-to-API wiring, auth storage,
    responsive navigation, routing and accidental removal of any required
    origination lifecycle step.
    """
    required_paths = {
        '/api/v1/borrower-registration/',
        '/api/v1/origination/borrowers/{borrower_id}/financial-profile',
        '/api/v1/origination/applications',
        '/api/v1/origination/applications/{application_id}/assess',
        '/api/v1/origination/applications/{application_id}/submit',
        '/api/v1/professional/direct-applications/{application_id}/approve',
        '/api/v1/origination/loans/{loan_id}/contract',
        '/api/v1/loans/{loan_id}/disburse',
        '/api/v1/loans/{loan_id}/installments/{installment_id}/payments',
        '/api/v1/loans/repayments',
        '/api/v1/auth/mfa/status',
        '/api/v1/auth/sessions',
        '/api/v1/controls/summary',
        '/api/v1/controls/payment-adjustments',
        '/api/v1/controls/accounting-periods',
        '/api/v1/controls/bank-statement-lines',
        '/api/v1/controls/audit-integrity',
        '/api/v1/controls/data-rights',
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(f'{WEB}/login', wait_until='networkidle')
        page.locator('#login-phone').fill(PHONE or '')
        page.locator('#login-password').fill(PASSWORD or '')

        with page.expect_response(
            lambda response: (
                response.request.method == 'POST'
                and response.url.rstrip('/').endswith('/api/v1/auth/login')
            ),
            timeout=20_000,
        ) as login_info:
            page.get_by_role('button', name='Login to LoanHub').click()

        login_response = login_info.value
        if not login_response.ok:
            detail = 'no API detail returned'
            try:
                payload = login_response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get('detail') or detail)
            except Exception:
                pass
            browser.close()
            pytest.fail(
                f'Browser login API failed with HTTP {login_response.status}: {detail}'
            )

        try:
            page.wait_for_url(lambda url: '/login' not in url, timeout=20_000)
        except PlaywrightTimeoutError:
            current_url = page.url
            visible_text = page.locator('body').inner_text()[:800]
            browser.close()
            pytest.fail(
                'Browser login API succeeded but the UI did not leave /login. '
                f'Current URL: {current_url}. Visible UI: {visible_text!r}'
            )

        expect(page.locator('body')).not_to_contain_text('Invalid phone number or password')

        access_token = page.evaluate("window.localStorage.getItem('access_token')")
        assert access_token, 'Browser login did not persist the API access token'

        # Phone: LoanHub should behave like an app with a persistent bottom bar,
        # safe viewport sizing and a complete touch-friendly More tools sheet.
        page.set_viewport_size({'width': 390, 'height': 844})
        mobile_nav = page.locator('[data-loanhub-mobile-nav="true"]')
        expect(mobile_nav).to_be_visible(timeout=10_000)
        expect(page.locator('html')).to_have_attribute('data-loanhub-mobile-app', 'true')
        assert page.evaluate(
            'document.documentElement.scrollWidth <= window.innerWidth + 1'
        ), 'Phone layout introduces page-level horizontal overflow'

        # Verify the browser's actual scrolling element rather than relying on a
        # hard-coded app-root ID. A temporary body-level flex item guarantees a
        # tall document even when the current dashboard contains little data.
        mobile_scroll = page.evaluate(
            """() => {
                const scroller = document.scrollingElement;
                if (!scroller) return { ok: false, reason: 'scrollingElement missing' };

                const probe = document.createElement('div');
                probe.id = 'loanhub-mobile-scroll-probe';
                probe.style.display = 'block';
                probe.style.flex = '0 0 1800px';
                probe.style.height = '1800px';
                probe.style.width = '1px';
                probe.style.pointerEvents = 'none';
                probe.setAttribute('aria-hidden', 'true');
                document.body.appendChild(probe);

                window.scrollTo(0, 0);
                const before = scroller.scrollTop;
                const scrollHeight = scroller.scrollHeight;
                const clientHeight = scroller.clientHeight;
                window.scrollTo(0, scrollHeight);
                const after = scroller.scrollTop;
                const htmlOverflow = getComputedStyle(document.documentElement).overflowY;
                const bodyOverflow = getComputedStyle(document.body).overflowY;
                const mainOverflows = Array.from(document.querySelectorAll('main'))
                    .map((element) => getComputedStyle(element).overflowY);

                probe.remove();
                window.scrollTo(0, 0);

                return {
                    ok: scrollHeight > clientHeight && after > before,
                    before,
                    after,
                    scrollHeight,
                    clientHeight,
                    scrollingTag: scroller.tagName,
                    htmlOverflow,
                    bodyOverflow,
                    mainOverflows,
                };
            }"""
        )
        assert mobile_scroll['ok'], f'Document cannot vertically scroll on phone: {mobile_scroll}'
        assert mobile_scroll['scrollingTag'] in {'HTML', 'BODY'}, mobile_scroll
        assert mobile_scroll['htmlOverflow'] in {'auto', 'scroll'}, mobile_scroll
        assert mobile_scroll['bodyOverflow'] in {'visible', 'auto'}, mobile_scroll
        assert all(value not in {'hidden', 'clip'} for value in mobile_scroll['mainOverflows']), mobile_scroll

        page.get_by_test_id('mobile-nav-more').click()
        more_sheet = page.get_by_test_id('mobile-nav-more-sheet')
        expect(more_sheet).to_be_visible()
        expect(more_sheet.get_by_role('link', name='All companies')).to_be_visible()
        more_sheet.get_by_role('button', name='Close tools').click()
        expect(more_sheet).to_be_hidden()

        # Tablet/compact screens inherit the app navigation; desktop returns to
        # the existing sidebar/full workspace experience.
        page.set_viewport_size({'width': 820, 'height': 1180})
        expect(mobile_nav).to_be_visible()
        assert page.evaluate(
            'document.documentElement.scrollWidth <= window.innerWidth + 1'
        ), 'Tablet layout introduces page-level horizontal overflow'

        page.set_viewport_size({'width': 1280, 'height': 900})
        expect(mobile_nav).to_be_hidden()

        me = page.request.get(
            f'{API}/api/v1/auth/me',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        assert me.ok, f'Authenticated browser/API session failed: {me.status}'

        openapi = page.request.get(f'{API}/openapi.json')
        assert openapi.ok
        paths = set(openapi.json()['paths'])
        missing = required_paths - paths
        assert not missing, f'Missing lending lifecycle API paths: {sorted(missing)}'
        browser.close()
