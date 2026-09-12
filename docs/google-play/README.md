# LoanHub Android — Google Play Release Guide

This is the release handover for the LoanHub Android super-app in `apps/call_mobile`. The app serves LoanHub platform users, participating businesses and staff, borrowers/clients, and interested customers according to their authenticated permissions.

## Release identity

- Play app name: **LoanHub**
- Android package: **`ls.ithute.loanhub`**
- Version: **`1.0.0+1`** until the first uploaded Play version requires an increment
- Compile SDK: **API 37**
- Target SDK: **Android 16 / API 36**
- Upload format: **Android App Bundle (`.aab`)**
- Suggested category: **Business**
- Ads: **No**
- Audience: financial-services/business users; not designed for children

Treat `ls.ithute.loanhub` as permanent once the Play Console application is created. Every subsequent upload must increase the version code.

## 1. Play App Signing and upload key

Create LoanHub in Google Play Console with package `ls.ithute.loanhub` and enable Play App Signing.

Generate the private upload key once from `apps/call_mobile`:

```bash
keytool -genkeypair -v \
  -keystore android/upload-keystore.jks \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -alias upload

cp android/key.properties.example android/key.properties
```

Replace every `CHANGE_ME`. Never commit `android/key.properties`, the `.jks`, Firebase service-account credentials, payment-provider secrets or telephony-provider secrets.

## 2. Production LoanHub server

The store build requires the public production HTTPS LoanHub server:

```bash
export LOANHUB_API_URL=https://YOUR-PRODUCTION-LOANHUB-DOMAIN
```

Production clear-text HTTP is disabled. The backend must be reachable by Play reviewers and authorised test users.

## 3. Realtime/background notification configuration

Foreground realtime uses LoanHub's authenticated WSS endpoint. Background or terminated-app notification delivery uses Firebase Cloud Messaging as a transport while LoanHub owns the notification event contract, channels, sound/vibration and tap routing.

Export the public Android Firebase client values before building:

```bash
export LOANHUB_FIREBASE_PROJECT_ID=...
export LOANHUB_FIREBASE_APP_ID=...
export LOANHUB_FIREBASE_API_KEY=...
export LOANHUB_FIREBASE_MESSAGING_SENDER_ID=...
```

The release script requires all four values. They are passed to Dart and also become the Android native Firebase resource values needed when Android starts the process for a background notification.

The backend separately needs server-side credentials:

```text
FIREBASE_PROJECT_ID=...
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/loanhub-firebase-service-account.json
```

The service-account JSON is a private deployment secret and must never be committed to the app or repository.

See `docs/mobile/REALTIME_ARCHITECTURE.md` for the complete event/background design.

## 4. Build the signed production AAB

Run:

```bash
cd apps/call_mobile
bash scripts/build_play_bundle.sh
```

The guarded script validates upload signing, requires the HTTPS API and Firebase client configuration, resolves Flutter dependencies, checks Dart formatting/analyzer/tests, then builds the signed release bundle.

Expected output:

```text
apps/call_mobile/build/app/outputs/bundle/release/app-release.aab
```

Do not upload a CI AAB as production signing material. Build the store upload locally with the private upload key.

## 5. Play Console declarations

Complete and verify at submission time:

- **App access:** provide a stable fictional reviewer account/demo environment.
- **Data safety:** use `DATA_SAFETY.md` as the engineering map and verify it against the final Firebase, payment, telephony, storage and backend configuration.
- **Privacy policy:** deploy `/privacy/loanhub-mobile` on the public HTTPS LoanHub frontend.
- **Financial features:** describe chats, lending-service access and provider-backed money flows accurately; do not describe pending transfer instructions as settled funds.
- **Permissions:** disclose Contacts, Microphone and Notifications as implemented.
- **Content rating, target audience and ads:** complete with the final production behavior.
- **Account deletion:** LoanHub now permits interested users to create a basic account in-app, so the current Google Play account-deletion requirements must be satisfied before production release.

## 6. Reviewer/demo access

The reviewer environment should contain only fictional data and allow Google to reach the meaningful app experience without human approval during review.

Where applicable provide demo access for:

- sign-in and interested-client onboarding;
- Chats and a test conversation;
- LoanHub Money screens without implying settlement when the test provider is unavailable;
- company calling tools for an eligible test staff role;
- Contacts and Microphone permissions;
- Notifications permission and a safe test message/realtime event.

Never put reviewer passwords in the public repository. Enter them only in Play Console App access.

## 7. Store listing assets

Prepare and upload:

- final 512 × 512 LoanHub store icon;
- feature graphic;
- phone screenshots for Landing/Sign in, Chats, Calls, Money, Explore and Profile;
- optional tablet screenshots if tablet availability remains enabled;
- developer/support contact details;
- public privacy-policy URL.

Use fictional names, phone numbers, loans, messages, balances and payment records in screenshots.

## 8. Recommended release sequence

1. Create/verify the Play developer account.
2. Create **LoanHub** with package `ls.ithute.loanhub` and enable Play App Signing.
3. Deploy the production HTTPS backend/frontend and privacy-policy page.
4. Configure production PostgreSQL/Redis and apply Alembic migrations.
5. Configure Firebase server credentials and the Android public Firebase client values.
6. Configure payment-provider and LiveKit/SIP/Vodacom services that are ready for production.
7. Generate/back up the upload key and configure `android/key.properties`.
8. Run `bash scripts/build_play_bundle.sh`.
9. Create the fictional reviewer/demo accounts/data.
10. Complete App access, Data safety, Financial features, account deletion and all remaining App content declarations.
11. Upload the signed AAB to **Internal testing** first.
12. Test the Play-installed build on real Android devices: sign-in, chats, foreground realtime, background message ringing, provider-confirmed money notification, notification tap routing, contacts, calls, offline/reconnect recovery and sign-out.
13. Review Play pre-launch/policy reports, then promote through the required testing/production tracks.

## 9. Release update rule

After version code `1` is uploaded, increment for every later Play upload, for example:

```yaml
version: 1.0.1+2
```

Never reuse a version code already accepted by Play Console.

## Related documents

- `STORE_LISTING.md` — Play listing copy
- `DATA_SAFETY.md` — Data Safety implementation mapping
- `APP_ACCESS.md` — reviewer login template
- `docs/mobile/REALTIME_ARCHITECTURE.md` — socket/BLoC/background push architecture
- `apps/call_mobile/README.md` — developer/build documentation
- `docs/VODACOM_LESOTHO_LOANHUB_TELEPHONY_REQUEST.md` — telephony-provider requirements
