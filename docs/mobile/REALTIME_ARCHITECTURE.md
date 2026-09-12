# LoanHub Mobile Realtime Architecture

LoanHub mobile uses one event architecture for foreground sockets, BLoCs, background push wakeups and native notifications.

## Event flow

```text
LoanHub backend domain event
          |
          v
Authenticated /api/v1/ws
          |
          +--------------------> foreground Flutter app
          |                         |
          |                         v
          |                   RealtimeBloc
          |                    /    |    \
          |                   /     |     \
          |             ChatBloc MoneyBloc NotificationBloc
          |
          +--------------------> FCM high-priority push
                                    |
                                    v
                            Android notification channels
                            - LoanHub Messages
                            - LoanHub Money
                            - LoanHub Calls
                            - LoanHub Updates
```

The WebSocket is the foreground realtime path. Android is allowed to suspend or kill background applications, so LoanHub deliberately does **not** claim that a WebSocket can remain alive indefinitely in the background. When the app leaves the foreground it closes the socket and uses push for wake/notification delivery. On resume it reconnects and performs an API catch-up. WorkManager remains a low-frequency recovery mechanism.

## Event contract

New typed events use the `loanhub.realtime.v1` envelope:

```json
{
  "type": "MONEY_RECEIVED",
  "event_id": "uuid",
  "domain": "money",
  "occurred_at": "2026-08-20T15:00:00Z",
  "entity_id": "payment-uuid",
  "data": {},
  "notification": {
    "category": "money",
    "title": "Money received",
    "body": "LSL 250.00 received in LoanHub",
    "route": "money:payment-uuid"
  }
}
```

Existing web clients remain compatible because important `data` fields are mirrored at the top level where necessary. Every event sent through the user WebSocket path receives an event ID and inferred domain. The mobile repository deduplicates matching socket and push copies by event ID.

## Mobile BLoCs

- `RealtimeBloc` owns connection state and receives every event delivered to the mobile socket.
- `ChatBloc` owns conversation/unread state and reacts immediately to chat events.
- `MoneyBloc` owns transfer/configuration state and reacts immediately to money/payment events.
- `NotificationBloc` owns notification tap routing.

The super-app shell reads BLoC state. It no longer runs periodic chat/unread polling timers. A manual pull-to-refresh remains as a recovery/user action.

## Background notifications

LoanHub owns Android notification UX in `MainActivity.kt`; no generic local-notification plugin controls the channels.

Channels:

- `loanhub_messages` — high importance, sound + vibration.
- `loanhub_money` — high importance, sound + vibration.
- `loanhub_calls` — high importance, sound + vibration.
- `loanhub_events` — default general updates.

Android 13+ asks for `POST_NOTIFICATIONS`. Tapping a notification routes the app to Chats, Money or Calls through `NotificationBloc`.

## Firebase transport configuration

FCM is only the delivery/wake transport. No Firebase credential is stored in the APK repository.

### Backend

Configure the deployment environment with:

```text
FIREBASE_PROJECT_ID=your-firebase-project-id
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/loanhub-firebase-service-account.json
```

`GOOGLE_APPLICATION_CREDENTIALS` must point to a deployment secret, not a committed repository file. When `FIREBASE_PROJECT_ID` is absent, the backend starts normally and foreground WebSocket realtime still works; background push delivery is simply disabled.

### Android app

Build the app with these public Firebase client identifiers:

```bash
flutter run \
  --dart-define=LOANHUB_FIREBASE_PROJECT_ID=... \
  --dart-define=LOANHUB_FIREBASE_APP_ID=... \
  --dart-define=LOANHUB_FIREBASE_API_KEY=... \
  --dart-define=LOANHUB_FIREBASE_MESSAGING_SENDER_ID=...
```

Use the same defines for the release AAB. These identifiers are Firebase client configuration, not the server private key. The service-account/private credentials remain server-side only.

After an authenticated session starts, the app registers its current FCM token against `/api/v1/realtime/devices/register`. Token refreshes update the same device record. Sign-out revokes that device registration when network connectivity permits.

## Message notifications

Existing encrypted LoanHub chat remains authoritative. `CHAT_MESSAGE_CREATED` is delivered over the existing user WebSocket path. The realtime push bridge also sends a high-priority message notification to recipients other than the sender. The phone rings/vibrates according to the user's Android notification settings.

Typing indicators use the same socket with `CHAT_TYPING` and do not write database rows.

## Money notifications

Creating a LoanHub Money transfer produces `MONEY_TRANSFER_CREATED`; it does **not** produce a success notification.

`MONEY_RECEIVED` is generated only after the verified LelefaPayGate webhook path updates the matching `PaymentTransaction` to `SUCCEEDED`. LoanHub resolves recipients from server-owned user, borrower, company and payment records. A payment-level marker prevents multiple succeeded webhook variants from ringing the same payment twice.

This preserves the rule that creating a transfer instruction is not equivalent to settlement.

## Delivery limitations

- Foreground: WebSocket delivery is intended to be immediate, subject to network connectivity.
- Background/terminated: FCM can wake/show notifications, subject to Android/Google Play services, network, user notification settings and OEM battery policies.
- Force-stopped app: Android may block background delivery until the user opens the app again. LoanHub cannot override that operating-system rule.
- Offline gaps: resume reconciliation and WorkManager catch-up restore authoritative API state.

## Database migration

Run normal LoanHub migrations after deploying this change. Migration `c4t7u9v1w245` creates the authenticated mobile push-device registry.
