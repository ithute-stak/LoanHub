# LoanHub Google Play — App Access Instructions

LoanHub Mobile is login-gated. Google Play review must be given stable credentials and clear instructions that reach the real employee business-phone experience without requiring a reviewer to contact LoanHub staff manually.

## Play Console selection

In **App content → App access**, indicate that all or some functionality is restricted by login/authentication.

## Reviewer instruction template

Paste and complete a version of the following in Play Console. Do **not** commit real passwords or OTP secrets to this repository.

```text
LoanHub is an employee-facing business application. A pre-created review account is required.

Production/review server:
https://YOUR-REVIEW-OR-PRODUCTION-DOMAIN

Login phone:
[ENTER REVIEW PHONE IN PLAY CONSOLE ONLY]

Password:
[ENTER REVIEW PASSWORD IN PLAY CONSOLE ONLY]

OTP / 2FA:
[State "not required for this dedicated review account" OR give self-contained instructions that Google can complete without contacting us]

After signing in:
1. The Calls tab displays the test company's call dashboard and media/recording status.
2. Open Clients to see fictional test clients and loan references.
3. Tap SYNC to test optional Android Contacts permission and client contact synchronisation.
4. Tap CALL on a fictional client to reach the active-call interface. A live telephone call requires the configured test SIP/media provider.
5. The active-call interface includes Mute, Hold and Transfer controls.
6. Open Team to view fictional employee extensions/transfer destinations.
7. Open Profile to see the signed-in company/role and call-policy status.

All review data is fictional. No real borrower/customer information is used in the review account.
```

## Review-account requirements

The account should:

- remain enabled for the entire review period;
- have one of LoanHub's permitted calling roles;
- use a non-production/demo company containing fictional clients;
- not require branch/company approval after login;
- not depend on a one-time OTP sent to a developer's private device;
- have at least two fictional employees so Transfer can be reviewed;
- have at least two fictional clients and loan references;
- have no real recordings or customer information;
- be connected to a safe test telephony destination if Google must exercise live calling.

## Before each submission

Test the exact reviewer credentials from a clean Android device or private browser/session. Confirm that:

- the server is publicly reachable;
- TLS certificate is valid;
- login succeeds;
- reviewer membership is active;
- Contacts Sync can be demonstrated;
- the app does not expose a local-development server address in the production release;
- the telephony provider does not place unexpected chargeable calls during review.

If telephony is not yet activated for the review tenant, explain this clearly in the reviewer notes and ensure the remaining UI can still be inspected. Do not claim that provider-gated functionality is live when it is not.
