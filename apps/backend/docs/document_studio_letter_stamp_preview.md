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

## Exact PDF candidate evidence (still non-routed)

The pure `document_studio_letter_pdf_binding.bind_letter_pdf_candidate`
function now checks the locked document's tenant, ID, version and HTML digest
before capturing SHA-256 of the *exact* source PDF and final candidate PDF
bytes. This is deterministic evidence for later comparison with an immutable
stored version, not itself proof of a valid or officially issued letter.

Important open controls: a trusted renderer must attest that the source PDF
actually derives from the locked HTML and approved dynamic assets; the
stamping/signing pipeline must retain the exact final candidate bytes, then
bind the digest and Object Lock VersionId to the issuer/audit transaction,
recheck authorization until COMMIT, and make public verification work.
A bare candidate digest must never be treated as final issuance.

## Document-controlled rendering snapshot

The source-lock and candidate-evidence path now also bind a canonical SHA-256
snapshot of the stored letter's PDF-relevant document settings, rather than
only its HTML. The comparison covers page size/orientation, margins, title,
reference, text, fonts, logo selection, header/footer flags, cover-page
configuration, address blocks and source version. Unknown runtime objects in
the snapshot fail closed. The trusted issuer must retain the persisted row
lock through issuance commit.

**Scope limitation:** This is a hash of document-controlled inputs, not the
source PDF bytes and not a cryptographic attestation of the rendering engine,
external company branding assets, dynamic timestamps or font deployment.
The eventual trusted renderer must freeze or independently bind those
dependencies, then link the actual final stored PDF hash and immutable
object version to the issuance record. This remains an unexposed draft
capability and must not be enabled for customer-facing letters.

## Legal identity and logo-byte evidence

The new pure `capture_letter_branding_evidence` helper records exact SHA-256
fingerprints for the two resolved logo byte streams and canonical company
identity fields, tied to the document tenant. The letter PDF candidate
binding now requires a tenant-matching branding evidence digest. Regression
tests prove that changing the logo bytes, legal name, registration, address
or other company contact details changes that fingerprint.

**Critical remaining boundary:** this helper takes already resolved bytes.
It must be connected to one trusted, frozen rendering operation that uses
exactly those bytes on every page and ties its output to an immutable
version in the final issuance transaction. Simply hashing two supplied
images does not prove that the actual PDF renderer used them; neither
does a snapshot certify company logo approval. Do not expose this as
official issuance without source-and-asset provenance, issuer authorization
and exact final PDF retention checks.

## Multi-page PDF logo consistency

The normal Document Studio PDF exporter now resolves the company's
`BrandingLogos` once per export and reuses those exact bytes in all page
header callbacks, instead of re-querying branding for every page. An explicit
document-level right logo still takes precedence as before. This prevents
different pages of one export from independently picking up logo changes.
The exported DOCX path and existing logo selection priorities are unchanged.

This is a step toward reliable renderer provenance, **not** proof that an
official stamp has been approved or that immutable final issuance is complete.
The eventual issuer must link the actual resolved logo-byte fingerprints,
letter source, PDF bytes, approved stamp and object-lock version atomically.
