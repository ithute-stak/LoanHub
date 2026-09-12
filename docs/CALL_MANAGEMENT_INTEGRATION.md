# LoanHub Call Management, Recording & Quality Assurance

## Purpose

This module integrates the employee call-tracking specification directly into LoanHub. Borrowers, company loans, staff, branches, roles and audit records remain owned by LoanHub; the call app does not maintain a competing client database.

## Architecture

```text
Employee Flutter app
        |
        | HTTPS/JWT + company/role scope
        v
LoanHub FastAPI
  |       |        |
  |       |        +--> LiveKit server API --> SIP trunk --> Client telephone
  |       +-----------> LiveKit room (WebRTC audio)
  +-------------------> PostgreSQL call metadata / QA / policy
  +-------------------> encrypted ManagedFile object storage (recording files)

LoanHub Next.js Calls & QA
        |
        +--> call register / playback / QA / performance / retention
        +--> subscribe-only LiveKit token for LISTEN ONLY monitoring
```

## Existing LoanHub data reused

- `CompanyStaff` identifies the employee and active role.
- `CompanyBranch` supplies branch scope.
- `Borrower` is the global LoanHub borrower identity.
- `ClientCompanyLoan` links the borrower to the company and loan.
- `ManagedFile` stores encrypted confidential recording objects.
- `AuditLog` records recording playback, live monitoring, legal holds, policy changes and media actions.

## New tables

- `call_management_policies`
- `employee_call_devices`
- `client_calls`
- `call_recordings`
- `recording_legal_holds`
- `call_quality_reviews`

Alembic revisions:

- `c2r6t8u0v133` — core call management tables.
- `c3s6t8u0v134` — company SIP routing fields.

## Security rules

1. Every request is company-scoped and branch-restricted where the active role is branch-limited.
2. Employees can create and update only calls assigned to their own LoanHub staff membership.
3. Managers/reviewers receive a subscribe-only LiveKit token for listen-only monitoring; they cannot publish into the room through that token.
4. Recordings are accepted only when recording is enabled by company policy and the controlled media provider is configured.
5. Recording files use LoanHub `ManagedFile` confidential/encrypted storage, not PostgreSQL blobs.
6. Playback is audited and never extends `deletion_at`.
7. Legal holds prevent the retention worker from deleting a recording while the hold is active.
8. The retention worker removes the stored object, marks the managed file deleted, marks the recording deleted and keeps call metadata/audit history.
9. LiveKit API key/secret are deployment secrets. They are never returned to the web or mobile client.
10. Outbound SIP trunk IDs are company routing configuration; SIP credentials remain with the media/SIP provider configuration rather than the employee app.

## Outgoing call flow

```text
Employee chooses LoanHub borrower + loan
    -> POST /call-management/calls
    -> LoanHub creates idempotent call + private media room name
    -> employee receives short-lived publish/subscribe room token
    -> Flutter joins LiveKit and publishes microphone
    -> POST /call-management/calls/{id}/dial
    -> LoanHub Server API creates SIP participant using company outbound trunk
    -> PSTN/SIP client joins same room
    -> call ends
    -> LoanHub closes media room and stores duration/outcome/notes
```

## Incoming call flow

The database/API model supports incoming calls and safe phone matching. Production PSTN inbound routing still requires the selected SIP provider/LiveKit inbound trunk and dispatch-rule configuration so the incoming SIP participant is routed to the appropriate LoanHub employee device. Do not emulate this with hidden Android SIM-call interception.

The provider integration must deliver enough trusted call context for LoanHub to create an incoming `ClientCall`, normalize the number and apply the "one unique borrower match only" rule. If several LoanHub borrowers share a number, the app must require employee selection instead of silently assigning the call.

## Recording production path

The current API accepts a recording produced by the controlled call path and saves it as a confidential LoanHub managed file. For production automation, configure LiveKit Egress/media recording and have the trusted server-side integration register/upload the completed recording. Do not source the recording from arbitrary Android cellular-call capture.

## Retention

`recording_deletion_at` is calculated when the recording is created. The maintenance worker checks expired `available` rows, skips active legal holds, deletes the object and records `RECORDING_DELETED`.

Playback has no code path that changes the deletion timestamp.

## Manager workspace

Route:

```text
/company/calls
```

Provides:

- today's call KPIs;
- company/branch call register;
- recording playback;
- live call list;
- listen-only monitoring;
- employee activity comparison;
- quality score/compliance/customer-care review;
- recording/monitoring/retention policy controls.

## Mobile module

Path:

```text
apps/call_mobile
```

The source is Flutter/Dart and uses:

- `livekit_client` for WebRTC audio;
- `flutter_secure_storage` for the LoanHub access token and tenant selection;
- `sqflite` for pending call metadata;
- `workmanager` for Android background synchronization.

See `apps/call_mobile/README.md` for Android platform generation and release setup.

## Deployment checklist

1. Apply Alembic migrations through `c3s6t8u0v134`.
2. Configure encrypted LoanHub file/object storage.
3. Deploy LiveKit (Cloud or self-hosted) and inject server API credentials.
4. Configure the selected SIP provider and LiveKit outbound trunk.
5. Store the company outbound trunk ID and approved caller number in Call Management SIP settings.
6. Configure inbound trunk/dispatch for incoming PSTN calls before enabling incoming production routing.
7. Configure server-side recording/egress and trusted recording upload.
8. Review company recording notice, retention period, legal-hold rules and permitted monitoring roles before enabling recording or live monitoring.
9. Generate the Flutter Android platform shell, add current microphone/audio permissions, run `flutter analyze`, build and device-test.
10. Run LoanHub backend tests, Alembic validation, frontend typecheck/lint/build and browser E2E before merging.
