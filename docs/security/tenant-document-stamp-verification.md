# LoanHub tenant document stamps and authenticity verification

Status: implementation specification — **not deployed**. The existing PDF generation, company configuration, document studio, and storage paths must be located and reviewed before wiring this into production.

## Product boundaries
- LoanHub owns *all* document stamp generation, issuance, verification, audit records, and configuration.
- IthuteSign stays signature-only. Do not add stamp composition to IthuteSign or change its Wacom capture workflow.
- Each LoanHub tenant configures its own legal/company identity and stamp appearance in Company Configuration.
- Batlokoa Financial Services (Pty) Ltd is the first reference configuration. The 2026-11-17 photographed ink stamp has telephone numbers +266 63887631 / 56521995, email batlokoafinancialservices@gmail.com, and Kingsway Road, Victoria Hotel Room 111. Require the tenant administrator to verify the exact legal name, address and contact details before saving; do **not** silently seed unverified values into production.
- Date is generated from issuance event, with timezone Africa/Maseru, never hard-coded from the photograph.

## Coverage and release safety
- Inventory every LoanHub document entrypoint: Document Studio, loan agreement, application, statements, receipts, repayment schedule, letters, notices, generated exports, and downloadable regenerated copies. Identify documents intentionally excluded by legal/policy requirements.
- Create one server-side finalization service used by all generation paths. Apply the tenant stamp and security legend before finalization and compute the integrity proof on the **final PDF bytes**.
- Preserve previously issued documents. For older documents, display 'legacy: not cryptographically verified' rather than forging a retroactive issuance record.
- For signature workflows, finalize stamped version *before* sending to IthuteSign; the subsequently signed PDF is a **new version** recorded with its own hash and related signing event. Never alter signed bytes in-place, because doing so would invalidate any cryptographic signatures.
- Fail closed when tenant config is incomplete, stamp application fails, issuance persistence fails, or proof creation fails. Never return an unstamped document as 'verified'.
- Scope all records and downloads to tenant; require authorization to issue/reissue/revoke, prevent cross-tenant leakage.

## Tenant configuration (suggested)
`company_stamp_settings`: tenant_id, legal_name, trading_name, registration_number, physical_address, postal_address, phone_numbers, email, logo_asset_id, optional stamp_asset_id, accent_color, enabled, version, approved_by, approved_at, updated_at.
Use existing Company Configuration as source of truth rather than duplicating contact data unnecessarily. Stamp asset must be vetted server-side; do not accept arbitrary executable SVG. Log edits and approvals; never grant ordinary staff permission to change official details.

## Issuance and verification
`document_issuances`: id (UUID), public_document_id (random/non-enumerable), tenant_id, source_document_type, source_record_id, version, stamp_config_version, original_artifact_id, final_artifact_id, final_sha256, created_at, issued_by, status (issued/revoked/superseded), revoked_reason, prior_issuance_id, signature_status.

- The PDF shows full approved company details, date, short ID, and a QR pointing to `https://<approved-host>/verify/<unguessable-public-id>`; route host must come from trusted server configuration, never user input.
- The QR and visual stamp are **identifiers, not unforgeable proof**. The verification page must look up an authoritative issuance record and report tenant, document type, issue timestamp, current revocation/supersession status and (if authorized or uploaded for checking) whether PDF bytes match the stored SHA-256.
- Never expose full loan/customer contents, national IDs, or confidential financial fields on a public verification page.
- An authentic QR copied onto a forged document can still point to a legitimate record; therefore offer an upload-to-verify or trusted in-app validation flow that recomputes the exact PDF hash. Store/uploads must be short-lived and protected.
- For stronger independently verifiable authenticity, add a trusted certificate-based PAdES PDF signature using securely managed keys, with timestamping as appropriate. A drawn stamp/QR alone is not a digital signature.
- Hashes are of the final bytes, not prior draft bytes; avoid recursive embedding of the final hash in the PDF itself. Use immutable issuance metadata and separately stored hash.

## Verification display states
Verified exact bytes / Issued but bytes not checked / Altered or unrecognized file / Revoked / Superseded / Legacy unverified / Service unavailable.
Never call a document verified solely because its QR resolves.

## Offline and availability
- Generation and signing can continue only through an explicitly authorized offline-draft path. Until server issuance and proof storage succeed, label it 'DRAFT / NOT VERIFIED', disallow official distribution and queue safe reconciliation. Never claim an offline document is officially verified.
- Preserve audit trail, idempotency token and stable issuance ID across retries. Never create duplicate official issuance entries from a retry.

## Acceptance tests
1. Two tenants with distinct stamps: no cross-tenant fields/assets/verification exposure.
2. Every production document type passes finalization once; no double-stamping or page clipping.
3. Changing one byte of PDF fails upload hash verification; copied QR cannot falsely verify an altered PDF.
4. Tampering tenant date, swapping stamp, or editing a generated PDF is detected by exact-byte verification and/or cryptographic signature.
5. Revoked/superseded documents resolve with correct status.
6. Reissuing creates a new immutable version and leaves old artifact intact.
7. Stamp fits A4/letter, multi-page, scanned and landscape PDFs; accessible text remains readable.
8. Non-admin cannot edit stamp config; every change is audited.
9. No customer PII is emitted by anonymous verification.
10. Wacom signature capture and offline IthuteSign behavior are unchanged.
11. Failure to create proof or persist issuance never serves a PDF as verified.
12. Existing legacy artifacts remain accessible without misleading verification badges.

## Safe implementation order
1. Audit generation endpoints + Company Configuration model and authorization policy.
2. Add tenant stamp config validation/UI and Batlokoa setup after admin confirmation.
3. Build reusable PDF stamp renderer and coverage tests.
4. Introduce immutable issuance table, checksum and revocation states.
5. Add QR/verification portal and exact-file verification.
6. Integrate with Document Studio and every other generation/export flow.
7. Integrate signed-document version linkage (IthuteSign unchanged).
8. Run staged migration, tests, tenant-by-tenant rollout with feature flag, then deploy after review.
