# LoanHub Document Studio — Backend

This backend contains the complete FastAPI, PostgreSQL and Alembic implementation for LoanHub's shared document workspace.

## Included capabilities

- Authenticated workspace documents for borrowers, company users, platform users and superadmins.
- Private, company and platform visibility rules.
- Per-user sharing with `view` or `edit` access.
- Optimistic version control, autosave support and revision checkpoints.
- Twelve starter document templates.
- Word-like page settings: A4/Letter, portrait/landscape, margins, default font, font size and line spacing.
- Seven visual document themes.
- Sanitised rich HTML plus lossless Tiptap JSON storage.
- Draggable signature/fillable fields preserved in revisions, Word exports, PDF exports and printed HTML.
- Branded headers with LoanHub and lender/company logos.
- Editable `.docx` export through `python-docx`.
- Branded PDF export through ReportLab.
- Publishing exported files into the existing encrypted LoanHub file centre.

## Important database migration

The Document Studio requires both migrations:

```text
s2d4e6f8a130_workspace_document_studio.py
t3e5f7a9b240_word_style_and_signature_fields.py
```

Apply them before using `POST /api/v1/workspace-documents`:

```bash
cd apps/backend
source .venv/bin/activate
alembic upgrade head
```

If the migration is not applied, document creation can return HTTP 500 because the workspace tables or style columns do not exist.

## Local setup

```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Create the required PostgreSQL database and configure `.env`, then generate or mount the RS256 keys expected by the project.

Run migrations:

```bash
alembic upgrade head
```

Start FastAPI:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info
```

## Verification

```bash
PYTHONPATH=. python -m compileall -q .
PYTHONPATH=. pytest -q tests/test_workspace_document_export.py
```

The isolated exporter tests verify HTML sanitisation, preservation of signature fields, Word generation and PDF generation.

## Main API endpoints

```text
GET    /api/v1/workspace-documents
POST   /api/v1/workspace-documents
GET    /api/v1/workspace-documents/{document_id}
PATCH  /api/v1/workspace-documents/{document_id}
DELETE /api/v1/workspace-documents/{document_id}

GET    /api/v1/workspace-documents/{document_id}/collaborators
POST   /api/v1/workspace-documents/{document_id}/collaborators
DELETE /api/v1/workspace-documents/{document_id}/collaborators/{user_id}

GET    /api/v1/workspace-documents/{document_id}/revisions
GET    /api/v1/workspace-documents/{document_id}/export/pdf
GET    /api/v1/workspace-documents/{document_id}/export/docx
POST   /api/v1/workspace-documents/{document_id}/publish
```

## Docker deployment

The included `compose.yaml` has a dedicated migration service. For a clean deployment:

```bash
docker compose build
docker compose up -d db redis
docker compose run --rm migrate
docker compose up -d api maintenance caddy
```

For an existing container deployment, always run the migration after pulling the new image:

```bash
docker compose exec api sh -lc 'cd /app && alembic upgrade head'
```

Adjust the container name/path to match your production Compose file.

## Security notes

- Do not commit `.env`, private keys, uploaded media, database dumps or generated secrets.
- Rich HTML is cleaned with Bleach and an explicit CSS allow-list.
- Data-URI images are size-limited during export.
- Visibility and edit permissions are enforced by the backend; frontend controls are not treated as security boundaries.
- Use HTTPS in production for authentication cookies, WebSockets and secure browser APIs.
