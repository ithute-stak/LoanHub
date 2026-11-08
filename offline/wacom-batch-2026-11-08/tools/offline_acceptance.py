#!/usr/bin/env python3
"""Static offline acceptance; dynamic tests require LoanHub and STU-540."""
from pathlib import Path
import ast

root=Path(__file__).resolve().parents[1]
policy=(root/'payload/apps/backend/services/wacom_document_policy.py').read_text()
router=(root/'payload/apps/backend/routers/wacom_document_intents.py').read_text()
models=(root/'payload/apps/backend/database/models/wacom_document_intent.py').read_text()
patch=(root/'apply_offline.py').read_text()
ui=(root/'payload/services/wacom-connector/loanhub_pc_document_ui.go').read_text()
for path in (root/'payload').rglob('*.py'):
    ast.parse(path.read_text(),filename=path.as_posix())
checks={
    'SHA256 document binding': 'LOANHUB-WACOM-DOCUMENT-V1' in policy,
    'Separate consent digest': 'LOANHUB-WACOM-CONSENT-V1' in policy,
    'Exact contract borrower authorization': 'LoanContract.borrower_id == body.borrower_id' in router,
    'Same-branch authorization': 'contract.loan.branch_id != ctx.branch_id' in router,
    'Server-managed document PDF': 'LoanContract.pdf_file_id == body.source_file_id' in router,
    'Source PDF checksum recertification at consent': 'current_pdf.checksum_sha256 != row.document_sha256' in router,
    'No implicit signing': '"signed_contract_created": False' in router,
    'Independent review': 'ctx.user.id == row.operator_user_id' in router,
    'Opt-in feature gate': 'LOANHUB_WACOM_DOCUMENT_INTENTS_ENABLED' in router,
    'DB evidence model': 'evidence_file_id' in models,
    'Go UI operator switch purge': 'session.forgetDocument()' in patch,
    'Go UI separate document workflow': 'documentConsentRequest' in ui,
    'No automatic database migrations': 'alembic upgrade head' not in patch,
}
for key,passed in checks.items():
    print(('PASS' if passed else 'FAIL'),key)
if not all(checks.values()):raise SystemExit(2)
