# Document Studio client-letter stamp preview (non-official)

The existing letter PDF export path is `services.workspace_document_service.export_pdf`.
Supported company client letters are identified by
`CLIENT_LETTER_TEMPLATE_KEYS`: confirmation, good standing, paid-up, and settlement.

A new **layout-only preview** is available when the server is explicitly
configured with `LOANHUB_LETTER_STAMP_PREVIEW_ENABLED=1`. It inserts a
tenant-bound stamp-like visual at the end of the PDF story, below the letter
body. It is clearly marked **NOT APPROVED OR VERIFIED — VISUAL PREVIEW ONLY**.
The setting defaults to disabled. It does not alter PDF or DOCX output when
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
