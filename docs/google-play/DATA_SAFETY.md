# LoanHub Mobile — Google Play Data Safety Mapping

This document maps the current implementation to the Google Play Data Safety questionnaire. It is an engineering aid, not a substitute for checking the final Play Console wording, production provider contracts and Google policy at submission time.

## Core principle

Answer the Play Console questionnaire for what the **production release actually does**, including the LoanHub backend and every third-party SDK/service that receives data from the app.

Re-check this document whenever authentication, LiveKit/SIP, payment providers, Firebase/notifications, analytics, crash reporting, advertising, contact sync or account flows change.

## Current app data flows

### Account and authentication information

Current processing can include:

- phone/sign-in identifier;
- password submitted to the LoanHub authentication endpoint;
- OTP when required;
- access token stored with Flutter Secure Storage;
- active user role, company and branch context;
- account/profile identifiers and display name.

LoanHub Mobile supports existing platform/company/borrower accounts and can create a basic interested-client account. Account creation does not approve credit.

Typical purposes: account management, authentication, security, app functionality and authorisation.

### Device and push-notification identifiers

Current processing can include:

- app-generated device UUID;
- operating system/platform and app version;
- Firebase Cloud Messaging registration token when background push is configured.

The FCM token is registered with LoanHub so the backend can deliver permitted background alerts. The push transport may process the token and minimal routing/notification data needed for delivery.

Typical purposes: app functionality, security/device management, fraud prevention, realtime/background notifications.

### Chat and communications data

Current processing can include:

- conversation participants and groups;
- encrypted stored message content;
- message timestamps, reply/edit/delete/read state;
- message previews used in notifications;
- file/voice-message metadata where supported;
- ephemeral typing and presence events.

Typical purposes: app functionality, communications, customer support and business operations.

### Financial and payment information

Current processing can include:

- loan/borrower references available to the authorised user;
- transfer type (C2C/C2B/B2C/B2B);
- amount and currency;
- payer/payee phone or LoanHub/business reference;
- payment provider, transaction/reference/status and audit data;
- provider-confirmed incoming-money amount in notifications.

Creating a transfer instruction does not mark funds as settled. `MONEY_RECEIVED` is emitted only after the verified payment-provider path confirms the matching payment as succeeded.

Typical purposes: app functionality, payments, lending/client service, fraud prevention, accounting/reconciliation and compliance/audit.

### Authorised client information

Current processing can include:

- client/borrower name and telephone number;
- LoanHub borrower/user identifier;
- loan identifier/reference;
- loan status, balance or overdue context where the signed-in role is permitted to see it.

This is protected LoanHub/company data, not public data.

### Contacts permission / device contacts

Contact sync is optional and starts when an authorised user selects Sync.

The implementation:

- reads phone numbers already in the Android address book to identify duplicates;
- writes authorised LoanHub client names/numbers into the address book;
- does not intentionally upload the user's pre-existing personal contact book to LoanHub through contact sync.

Distinguish local device access from data collected/transmitted off-device when completing the Play form, while still disclosing Contacts permission accurately.

### Microphone / audio

During an active controlled LoanHub call:

- microphone audio is transmitted to the configured realtime media/telephony service;
- other participant audio is received through the controlled media path;
- where an organisation's recording policy is enabled, the business call may be recorded by the configured media/PBX/provider service.

The app is not designed to covertly record ordinary Android SIM-call audio.

### Call and app activity data

Current processing can include:

- calling/called number;
- inbound/outbound direction;
- call status and start/answer/end timestamps;
- duration;
- company/branch/employee/device identifiers;
- client/loan association;
- transfer target/history;
- call outcome/notes;
- recording status/metadata.

Typical purposes: app functionality, business records, compliance/quality review, security and auditing.

### Offline/recovery data

Limited pending call metadata can be stored locally in SQLite and retried with WorkManager. Secure platform storage holds authentication/session values. WorkManager can also perform low-frequency API reconciliation after missed realtime/background events.

## Realtime and background delivery

Foreground events use an authenticated LoanHub WebSocket. Background/killed-app notification delivery uses Firebase Cloud Messaging when configured. LoanHub's Android code owns notification channels, notification permission, sound/vibration behavior and tap routing; Firebase is the delivery transport.

Current notification categories include:

- new chat messages;
- provider-confirmed incoming money/payment updates;
- call events when enabled;
- other important LoanHub events.

Android users can control notification permission, sound, vibration and visibility through system settings. Force-stopping the app may prevent background delivery until it is opened again.

## Encryption

The Google Play production build requires an HTTPS LoanHub API URL and disables clear-text traffic. Foreground realtime uses WSS for production. Live media is expected to use secure WSS/WebRTC transport.

SIP/PSTN encryption and payment-provider controls depend on the selected production providers. Do not claim provider-side protections in Play Console until verified for production.

## Third-party/service-provider review before submission

Re-check the final production configuration for:

- Firebase Cloud Messaging / Firebase Admin;
- LiveKit hosting/provider;
- Vodacom or another SIP/PSTN/PBX provider;
- LelefaPayGate and underlying payment/mobile-money/bank providers;
- object storage used for recordings/files;
- email/SMS/OTP providers;
- analytics, crash reporting or performance SDKs added later.

For each provider determine what data is transferred, why, whether it acts as a processor/service provider, retention/deletion behavior, and how Play classifies collection/sharing.

## Suggested Play Console mapping to verify

| Data area | Current implementation | Typical purpose |
| --- | --- | --- |
| User identifiers | Yes | Account management, security, app functionality |
| Phone number | Yes | Authentication, communications, payments/calling |
| Financial information | Yes, role-authorised lending/payment context | App functionality, payments, client service |
| Messages | Yes | Communications/app functionality |
| Contacts | Device contacts accessed locally for optional sync/deduplication | App functionality |
| Audio | Yes during controlled calls; recording depends on policy/provider | Calling, compliance/quality where enabled |
| App activity/call records | Yes | App functionality, audit/compliance |
| Device identifiers | Device UUID and push token/device details | Security, notifications, device management |
| Photos/videos/files | Chat/file support may process files when the feature is used | Communications/app functionality |
| Precise/approximate location | Not requested by current app | Not applicable unless later added |
| Advertising data | No advertising SDK in current app | Not applicable |

## User controls

Current controls include:

- Contacts permission can be denied; phone-book sync remains optional.
- Microphone permission can be revoked, although controlled calling then cannot use audio.
- Notification permission/sound/vibration can be disabled or adjusted in Android settings.
- Users can sign out; the app attempts to revoke the registered push device at sign-out.
- Company administrators control staff membership/access where relevant.
- Recording availability/retention is controlled by policy/backend configuration.

## Account deletion and data rights

Because the mobile app now allows interested users to create a basic account, verify Google Play's current account-deletion requirements before production submission and ensure the required in-app/web deletion route is available to eligible personal users.

Some financial, audit, legal-hold or contractual records may need to be retained even after an account-access request is completed. The privacy policy must explain the applicable process accurately.

## Final pre-submission verification

Before saving the Data Safety form, confirm:

- production backend domain and TLS are live;
- Firebase project and server credentials are configured securely;
- push notification categories/content match this disclosure;
- production payment and telephony providers are known;
- account-deletion flow satisfies the current Play policy for accounts created in-app;
- privacy policy matches final chat, money, call, notification and device-token flows;
- no analytics/crash/ads SDK has been added without updating this map;
- reviewer/demo data contains no real customer information;
- declarations match the permissions and SDKs inside the final uploaded AAB.
