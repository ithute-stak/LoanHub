#!/usr/bin/env python3
"""Conservative, local-only LoanHub patcher. Dry-run default; no network calls."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import pathlib
import shutil
import subprocess
import sys

BUNDLE = pathlib.Path(__file__).resolve().parent
PAYLOAD = BUNDLE / 'payload'


def substitute(src: str, old: str, new: str, name: str) -> str:
    if new in src:
        return src
    count = src.count(old)
    if count != 1:
        raise ValueError(f'{name}: incompatible upstream code (anchor occurrences={count})')
    return src.replace(old, new, 1)


def prepare(repo: pathlib.Path) -> dict[pathlib.Path, str]:
    base = repo/'apps/backend'
    for path in ('routers/wacom_bridge_device_proof.py', 'services/wacom_bridge_sessions.py',
                 'api/v1/router.py', 'database/models/__init__.py'):
        if not (base/path).is_file():
            raise ValueError(f'Required LoanHub baseline file missing: {path}')
    changes = {}
    # Register additive SQLAlchemy models before Alembic autoloads metadata.
    p = base/'database/models/__init__.py'
    orig = p.read_text()
    target = orig if 'from database.models.wacom_document_intent import WacomDocumentIntent' in orig else (
        orig + '\nfrom database.models.wacom_document_intent import WacomDocumentIntent\n')
    changes[p] = target
    # Keep the document evidence API opt-in. Never activate a signature engine.
    p = base/'api/v1/router.py'
    orig = p.read_text()
    if '    wacom_document_intents,\n' not in orig:
        orig = substitute(orig, '    wacom_bridge_device_proof,\n',
                          '    wacom_bridge_device_proof,\n    wacom_document_intents,\n', 'router import')
    if 'wacom_document_intents.router,' not in orig:
        orig = substitute(orig, 'wacom_bridge_device_proof.router, origination.router',
                          'wacom_bridge_device_proof.router, wacom_document_intents.router, origination.router', 'route registration')
    changes[p] = orig
    # Ensure active account even if the session token has not expired yet.
    p = base/'services/wacom_bridge_sessions.py'
    orig = p.read_text()
    a = '    if context.company_id is None or context.staff is None:\n        raise HTTPException(403, "Active company staff required")'
    b = ('    if context.company_id is None or context.staff is None or '
         'not getattr(context.user, "is_active", False):\n'
         '        raise HTTPException(403, "Active company staff required")')
    changes[p] = substitute(orig, a, b, 'active user check')
    # PR #632 may already be merged; only patch when missing.
    p = base/'routers/wacom_bridge_device_proof.py'
    orig = p.read_text()
    for model in ('WacomWorkstationEnrollment','WacomWorkstationOperator'):
        old = model+'.revoked_at.is_(None),\n    ).one_or_none()'
        new = model+'.revoked_at.is_(None),\n    ).with_for_update().one_or_none()'
        orig = substitute(orig,old,new,f'{model} proof/revocation serialization')
    changes[p] = orig
    # In strict local mode, reject legacy unprovisioned access to sensitive
    # routes, even though older deployments retain opt-out until tested.
    p = repo/'services/wacom-connector/loanhub_pc_client.go'
    orig = p.read_text()
    if '"os"' not in orig:
        orig = substitute(orig, '    "net/url"\n', '    "net/url"\n    "os"\n', 'Go os import')
    orig = substitute(orig,
        '    if protected && strings.HasPrefix(path,"/api/v1/local-signatures/") && c.workstationKeyDir != "" {',
        '    if protected && (strings.HasPrefix(path,"/api/v1/local-signatures/") || strings.HasPrefix(path,"/api/v1/wacom-document-intents")) && c.workstationKeyDir == "" && os.Getenv("LOANHUB_WACOM_PC_STRICT") == "1" {\n'
        '        return errors.New("Secure device identity required for Wacom PC API")\n'
        '    }\n'
        '    if protected && (strings.HasPrefix(path,"/api/v1/local-signatures/") || strings.HasPrefix(path,"/api/v1/wacom-document-intents")) && c.workstationKeyDir != "" {',
        'Go fail closed strict local mode')
    changes[p] = orig
    # Integrate the document workflow with existing secure Go localhost UI.
    p = repo/'services/wacom-connector/loanhub_pc_ui.go'
    orig = p.read_text()
    orig = substitute(orig, '    reviewQueue []LoanHubReviewCapture\n',
        '    reviewQueue []LoanHubReviewCapture\n    documentIntent *LoanHubDocumentIntent\n    lastDocumentCaptureID string\n',
        'Go PC session document state')
    orig = substitute(orig, '    ReviewQueue []LoanHubReviewCapture\n',
        '    ReviewQueue []LoanHubReviewCapture\n    DocumentIntent *LoanHubDocumentIntent\n    DocumentCaptureID string\n',
        'Go PC page document state')
    orig = substitute(orig, '        r.URL.Path != "/switch-operator" &&\n',
        '        r.URL.Path != "/switch-operator" &&\n'
        '        r.URL.Path != "/document-prepare" && r.URL.Path != "/document-consent" &&\n'
        '        r.URL.Path != "/document-attach" &&\n',
        'Go document endpoint allowlist')
    orig = substitute(orig, '        case "/refresh":\n',
        '        case "/document-prepare":\n'
        '            ui.documentPrepareRequest(ctx,r,session)\n'
        '        case "/document-consent":\n'
        '            ui.documentConsentRequest(ctx,r,session)\n'
        '        case "/document-attach":\n'
        '            ui.documentAttachRequest(ctx,session)\n'
        '        case "/refresh":\n',
        'Go local UI document handlers')
    orig = substitute(orig, '            session.reviewQueue=nil\n            if r.URL.Path == "/switch-operator" {',
        '            session.reviewQueue=nil\n            session.forgetDocument()\n'
        '            if r.URL.Path == "/switch-operator" {',
        'Go operator switching clears document context')
    orig = substitute(orig, '        ReviewQueue:session.reviewQueue,\n',
        '        ReviewQueue:session.reviewQueue,\n'
        '        DocumentIntent:session.documentIntent, DocumentCaptureID:session.lastDocumentCaptureID,\n',
        'Go page document state')
    orig = substitute(orig, '<section class="panel"><h2>Signature capture</h2>',
        '<section class="panel"><h2>Document-specific evidence</h2>\n'
        '<p>Review the EXACT contract PDF in LoanHub before requesting borrower consent. '
        'This desk collects evidence only; it never signs or changes a loan.</p>\n'
        '{{if .Client}}{{if .Client.Client}}\n'
        '<form method="post" action="/document-prepare"><input type="hidden" name="csrf" value="{{.CSRF}}">\n'
        '<label>Contract ID</label><input name="contract_id" required>\n'
        '<label>Contract PDF managed file ID</label><input name="source_file_id" required>\n'
        '<label>Document version (number)</label><input name="document_version" value="1" required>\n'
        '<button type="submit">Prepare exact document</button></form>{{end}}{{end}}\n'
        '{{if .DocumentIntent}}\n'
        '<p>Document SHA-256: <code>{{.DocumentIntent.DocumentSHA256}}</code></p>\n'
        '<p>State: {{.DocumentIntent.Status}} (not signed)</p>\n'
        '{{if eq .DocumentIntent.Status "prepared"}}\n'
        '<form method="post" action="/document-consent">\n'
        '<input type="hidden" name="csrf" value="{{.CSRF}}">\n'
        '<input type="hidden" name="displayed_sha256" value="{{.DocumentIntent.DocumentSHA256}}">\n'
        '<label>Consent evidence reference</label><input name="document_consent_reference" minlength="4" required>\n'
        '<label><input type="checkbox" name="signer_confirmed" value="yes" required style="width:auto"> '
        'Borrower has reviewed this exact document and explicitly confirmed consent</label>\n'
        '<button type="submit">Record exact-document consent evidence</button></form>{{end}}\n'
        '{{if .DocumentCaptureID}}<form method="post" action="/document-attach">\n'
        '<input type="hidden" name="csrf" value="{{.CSRF}}">\n'
        '<button type="submit">Link captured handwriting evidence to this document</button></form>{{end}}\n'
        '{{end}}</section>\n'
        '<section class="panel"><h2>Signature capture</h2>',
        'Go local HTML document desk')
    changes[p] = orig
    p = repo/'services/wacom-connector/loanhub_pc_capture_flow.go'
    orig = p.read_text()
    orig = substitute(orig, '    session.discardCapture()\n    if ui.sdkCapture==nil || session.client==nil {',
        '    session.discardCapture()\n'
        '    session.lastDocumentCaptureID=""\n'
        '    if ui.sdkCapture==nil || session.client==nil {',
        'Clear prior document capture on recapture')
    orig = substitute(orig, '    if enteredName=="" || !strings.EqualFold(',
        '    if session.documentIntent!=nil {\n'
        '        if kind!="client" || session.documentIntent.Status!="consented" ||\n'
        '            session.documentIntent.BorrowerID!=borrowerID {\n'
        '            session.feedback="Document intent and client capture do not match";return\n'
        '        }\n'
        '    }\n'
        '    if session.documentIntent!=nil && session.documentIntent.Status=="consented" &&\n'
        '        ref != session.documentIntent.ConsentReference {\n'
        '        session.feedback="Capture consent reference must match exact document consent";return\n'
        '    }\n'
        '    if enteredName=="" || !strings.EqualFold(',
        'Reject mismatched borrower document capture')
    orig = substitute(orig, '    session.discardCapture()\n    session.lastClient=nil\n    session.status=nil\n',
        '    if session.documentIntent!=nil && session.documentIntent.Status=="consented" &&\n'
        '        capture.signerKind=="client" && capture.borrowerID==session.documentIntent.BorrowerID {\n'
        '        session.lastDocumentCaptureID=receipt.FileID\n'
        '    }\n'
        '    session.discardCapture()\n    session.lastClient=nil\n    session.status=nil\n',
        'Go document capture receipt link')
    changes[p] = orig
    # Add separate file payload; refuse silently overwriting upstream changes.
    for src in PAYLOAD.rglob('*'):
        if not src.is_file():
            continue
        relative = src.relative_to(PAYLOAD)
        dst = repo/relative
        content = src.read_text()
        if dst.is_file() and dst.read_text() != content:
            raise ValueError(f'New file collides with existing upstream code: {relative}')
        changes[dst] = content
    return changes


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=pathlib.Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    if not (repo/'.git').exists():
        raise ValueError('A clean LoanHub Git checkout is required')
    result = subprocess.run(['git','status','--porcelain'],cwd=repo,capture_output=True,text=True,check=True)
    if result.stdout:
        raise ValueError('Git checkout is not clean; commit or stash before applying')
    changes = prepare(repo)
    todo = [(p,t) for p,t in changes.items() if not p.exists() or p.read_text() != t]
    print(f'Wacom full offline batch: {len(todo)} source files to change; dry run={not args.apply}')
    for path, text in todo:
        relative = path.relative_to(repo)
        print('+',relative)
        if path.exists():
            diff = ''.join(difflib.unified_diff(path.read_text().splitlines(True),text.splitlines(True),
                                                fromfile='a/'+str(relative),tofile='b/'+str(relative)))
            print(diff[:1800])
    if not args.apply:
        print('Dry run complete; no changes made.')
        return
    backup = BUNDLE/'local-backups'
    if backup.exists():
        raise ValueError('Backup directory already exists: refusing to overwrite previous backup')
    backup.mkdir(mode=0o700)
    for path,_ in todo:
        if path.exists():
            target = backup/path.relative_to(repo)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    for path,text in todo:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    print('Applied LOCALLY. No git commit, push, merge, migration or deployment performed.')


if __name__=='__main__':
    try:run()
    except Exception as exc:
        print('ABORTED:',exc,file=sys.stderr)
        sys.exit(2)
