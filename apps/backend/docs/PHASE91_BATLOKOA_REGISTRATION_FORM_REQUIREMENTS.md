# Phase 91 — Batlokoa client-registration form requirements (read-only)

An authenticated lending employee may access:

`GET /api/v1/batlokoa/registration/form-requirements`

The response returns only static form section names and approved field keys.
The field inventory is tested against `FullNewOnlyClientCapture`, so future
form changes require an explicit update to metadata rather than silently
omitting important financial or identity fields.

There are five intended screens: identity/contact, residence, employment
and income, banking/existing obligations, and client consent. Five
fields — email, temporary password, employer group ID/new group, and
CDAS employee number — are explicitly marked `deferred_fields` because
the protected full-registration writer currently rejects them. Do not
display these as available input controls until their persistence,
verification, and permission rules are separately implemented.

The endpoint accepts no borrower information, stores no draft, exposes
no customer data and contains no registration writer. It returns
`registration_available=false`, `submit_allowed=false`, and
`client_data_requested=false` unconditionally.

The existing tenant-authentication and active lending staff checks are
reused from Phase 90. A future mobile/web form can use the metadata to
arrange multiple screens, but **cannot submit** to the new-only writer
until approved identity indexes, production safety checks and full
release authorization are completed.

This API is informational and not an authorization decision.
Older assisted-client routes remain separate and must be reviewed
independently. No production migration or loan changes occur here.
