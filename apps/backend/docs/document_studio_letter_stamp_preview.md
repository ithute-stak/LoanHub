# Document Studio client-letter stamp preview (non-official)

The existing letter PDF export path is `services.workspace_document_service.export_pdf`.
Supported client letters are identified by
`CLIENT_LETTER_TEMPLATE_KEYS`: confirmation, good standing, paid-up, and settlement.
The layout preview also covers ordinary `formal_letter` and `business_letter`
templates.

A new **layout-only preview** is available when the server is explicitly
configured with `LOANHUB_LETTER_STAMP_PREVIEW_ENABLED=1`. It inserts a
tenant-bound stamp-like visual at the end of the PDF story, below the letter
body. It is clearly marked **NOT APPROVED OR VERIFIED — VISUAL PREVIEW ONLY**.
The setting defaults to disabled and is forbidden outside local, development,
or test environments even if enabled. Non-draft or finalized documents are
refused; official production PDFs cannot receive preview marks. It does not alter PDF or DOCX output when
disabled, does not sign or issue the letter, and does not create a QR code.

Do not enable this preview on production or use it as proof that a company
stamp has been approved. The authenticated company's final legal details must
be reviewed by an authorized administrator before official issuance.

## Production integration still blocked

For a real official company stamp, we must first introduce a reviewed
per-company approval and revocation lifecycle, check the current issuer,
bind the exact PDF and any signature to an immutable issuance record, and
test the production trusted issuer and storage policy. Once those gates are
certified, the preview flowable can be adapted to approved stamp rendering
rather than simply enabling the preview flag. Signed letters are explicitly
rejected from the preview path. Other letter generators remain unchanged.

## Regression checks

`apps/backend/tests/test_workspace_document_export.py` verifies disabled-by-
default behavior, visible preview labeling, letter-body ordering, cross-tenant
rejection, no stamp on contracts and rejection for already-signed documents.

## Read-only approval preflight (not routed)

`services.document_studio_letter_stamp_authorization.preflight_approved_letter_stamp`
now prepares evidence for a future trusted issuer. It checks that the letter,
company and authenticated tenant match; that the source is an unsigned draft
of a supported letter template; and that the issuer and version identifiers
are valid. Before it consults the approval registry it enforces the existing dedicated
issuer PostgreSQL login gate: actual `session_user` and `current_user` must
match a configured non-privileged login separate from `DB_USER`. This refuses
ordinary shared application SQL sessions even when tenant GUCs appear valid.
It then calls the existing protected PostgreSQL approval repository,
which is responsible for checking RLS, current SQL role privileges, independent
approver, approved content digest, expiry and revocation. Finally, it checks
the company snapshot again to catch an observable modification.

This helper **never renders or issues a document**, and it must not be called
directly from a new API endpoint without the remaining trusted issuer
authorization, transaction-lock continuity and immutable artifact binding.
An unsigned in-memory document is not proof that no stored signatures exist:
the eventual issuer must check and lock the persisted signature records.

A new CI step runs the PDF export regressions and this non-routed preflight's
denial and no-write tests. The official stamped-letter production path remains
blocked by the previously documented issuer and storage certification gates.

**Important limitation:** A distinct database login does not itself verify
human identity, make tenant GUCs unspoofable, or guarantee per-company
authorization. This remains non-routed and must run only inside a future
isolated issuer service after role, tenant, authorization and transaction
continuity controls are certified.

## Current issuer and transaction continuity

The non-routed letter preflight now also requires a real `TenantContext`
matching the supplied issuer, tenant and company. On the dedicated SQL
issuer connection it invokes `require_current_document_issuer`, which
reloads active User, approved LoanCompany and current management CompanyStaff
membership with PostgreSQL `FOR SHARE NOWAIT` row locks. It captures the
SQLAlchemy root transaction and actual PostgreSQL backend PID/transaction ID,
then verifies both are unchanged after the approval read.

This is an **in-transaction prerequisite** only, not a new endpoint. The
future trusted issuer must keep these locks alive through immutable PDF
binding and issuance COMMIT, and must prove that human identity cannot be
spoofed by ordinary shared application credentials. A passing non-routed
preflight is not an authorization token for later, separately transacted use.

## Locked persisted letter source (non-routed)

Before stamp approval lookup, the experimental preflight now invokes
`lock_current_letter_source`. This reloads the company's actual
`WorkspaceDocument` record under `FOR UPDATE NOWAIT`, compares its
version/template/body/status to the prepared draft and refuses deleted or
finalized records. It also checks for any persisted
`WorkspaceDocumentSignature` rows. Its source identity includes a SHA-256
fingerprint of the exact UTF-8 HTML stored in that locked version.

The exclusive parent row lock blocks concurrent FK-backed signature
insertions that need a key-share lock, **provided** the approved issuer retains
the same PostgreSQL transaction through the final issuance COMMIT.
This is intentionally stronger than a SELECT-only application runtime can do.
The dedicated issuer requires narrowly scoped UPDATE/row-lock privileges;
broad grants to the shared LoanHub runtime are prohibited.

A matching HTML digest is **not** a fingerprint of the finished PDF. An issuer
must independently validate rendered PDF bytes, dynamic branding/assets and
source metadata, any signing, immutable storage retention and ledger state.
These protections are not yet routed to the normal Document Studio export.
