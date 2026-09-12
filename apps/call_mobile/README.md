# LoanHub Business Phone

This Flutter application is the employee-facing LoanHub business softphone. It uses the employee's existing LoanHub company account and the company's controlled WebRTC/SIP telephony path to call ordinary telephone numbers.

Customers do **not** need LoanHub installed.

The app intentionally does not try to bypass Android or iOS protections to covertly intercept ordinary SIM-call audio. Reliable two-way recording, inbound routing, transfers and conferencing belong on the company SIP/PBX/media path.

## Google Play release identity

- App name: **LoanHub**
- Android package/application ID: **`ls.ithute.loanhub`**
- Version: **`1.0.0+1`**
- Compile SDK: **37**
- Target SDK: **36 (Android 16)**
- Play upload format: **Android App Bundle (`.aab`)**
- Production clear-text HTTP: **disabled**

See `docs/google-play/README.md` for the complete Play Console handover.

## Implemented mobile workflow

- Existing LoanHub company-account login and tenant/role reuse.
- Employee Android device registration.
- Authorized LoanHub client and loan lookup.
- Native phone-book synchronization for authorized LoanHub clients.
  - Contacts are labelled as LoanHub clients.
  - Existing matching telephone numbers are not duplicated.
  - Contact access is requested only when the employee chooses Sync.
- Outbound calls from LoanHub to normal telephone numbers through LiveKit/SIP/PSTN.
- Active call timer.
- Mute.
- Local employee hold/resume control while the PBX integration is being finalized.
- Team directory for LoanHub calling employees.
- Live SIP call transfer to another configured LoanHub employee.
- Recording-policy indicator.
- Call outcome and employee notes.
- Secure token storage.
- SQLite pending-call metadata queue.
- Android WorkManager background retry every 15 minutes.

## Provider-gated features

The application and backend are ready for the provider integration boundary, but these features require the production telephony service from Vodacom or another SIP/PBX provider:

- a public business DID/telephone number;
- inbound PSTN-to-SIP routing;
- employee extensions or SIP addresses;
- production caller-ID/CLI;
- simultaneous voice channels;
- provider/PBX-side automatic call recording;
- inbound call events/push delivery;
- provider CDR and recording retrieval APIs/webhooks;
- attended transfer and conference behavior where supported by the provider.

See `docs/VODACOM_LESOTHO_LOANHUB_TELEPHONY_REQUEST.md` for the technical/commercial provider request.

## Android development

The generated Android shell is committed under `android/`. Do not run `flutter create` during normal development.

From `apps/call_mobile`:

```bash
flutter pub get
dart format --output=none --set-exit-if-changed lib
flutter analyze
flutter run
```

Debug builds may use a local HTTP server such as `http://10.0.2.2:8000` on the Android emulator. Production releases do not permit clear-text HTTP.

## Build a Google Play release

### 1. Generate the private upload key once

```bash
keytool -genkeypair -v \
  -keystore android/upload-keystore.jks \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -alias upload
```

Then:

```bash
cp android/key.properties.example android/key.properties
```

Fill in the private key passwords/alias. Never commit `key.properties` or the `.jks` file.

### 2. Set the production HTTPS LoanHub server

```bash
export LOANHUB_API_URL=https://YOUR-PRODUCTION-LOANHUB-DOMAIN
```

The release build pins this compile-time address and rejects non-HTTPS production configuration.

### 3. Build the signed AAB

```bash
bash scripts/build_play_bundle.sh
```

Output:

```text
build/app/outputs/bundle/release/app-release.aab
```

The upload key is used only to authenticate uploads. Enable Google **Play App Signing** for the Play Console application.

## CI validation

`.github/workflows/validate-call-mobile.yml` validates:

- Flutter dependency resolution;
- Dart formatting;
- `flutter analyze`;
- production package `ls.ithute.loanhub`;
- compile SDK 37;
- target SDK 36;
- release version configuration; and
- an Android release `.aab` build.

CI intentionally uses temporary debug signing only to prove the release bundle compiles. The CI artifact is **not** the store upload. Build the production AAB locally with the private upload key.

## Android permissions

The release manifest declares the permissions required by the current business-phone client:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.READ_CONTACTS" />
<uses-permission android:name="android.permission.WRITE_CONTACTS" />
```

Contacts access is optional and requested when the employee selects Sync. Microphone access is used for the core controlled business-call experience.

The app launcher name is **LoanHub**.

## Privacy policy

The repository contains a public web privacy-policy route at:

```text
/privacy/loanhub-mobile
```

After deploying the production frontend, use the full public HTTPS URL in Google Play Console, for example:

```text
https://YOUR-LOANHUB-DOMAIN/privacy/loanhub-mobile
```

The privacy text must be rechecked whenever the production telephony provider, recording behavior, analytics SDKs or mobile permissions change.

## Required LoanHub media configuration

Backend runtime configuration:

```text
CALL_MEDIA_PROVIDER=livekit
LIVEKIT_URL=wss://your-livekit-host
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

Company management also configures its outbound SIP trunk ID and approved caller number through LoanHub call-management settings.

No LiveKit API secret or SIP provider password is sent to the mobile app. The backend keeps provider secrets and gives the app only short-lived room credentials.

## Employee transfer configuration

LoanHub uses provider-neutral telephony values in the employee profile `target_config` when available:

```json
{
  "telephony_extension": "201",
  "telephony_address": "sip:201@provider.example"
}
```

Aliases `extension` and `sip_uri` are also recognized. If no SIP address is configured, LoanHub can fall back to the employee's normal LoanHub phone number for a telephone transfer.

A SIP extension is preferred because it preserves PBX transfer and recording behavior more reliably.

## Offline behavior

If the employee has no connection while creating call metadata, the record is queued locally in SQLite with a device-generated UUID and WorkManager retries it later. LoanHub treats the UUID as an idempotency key so retries do not create duplicate call records.

A real PSTN/SIP call still requires network connectivity.

## iOS

This Play-release work applies to Android. The current repository contains the Android shell because Android is the current test target. The Flutter application logic is cross-platform, but an iOS shell, Contacts/Microphone usage descriptions, CallKit/incoming-call integration and iOS build/signing must be added and tested before an iPhone release.
