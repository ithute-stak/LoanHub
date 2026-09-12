# LoanHub Document Studio — Frontend

This frontend contains the complete Next.js Document Studio with a Microsoft Word-inspired editing experience.

## Editor capabilities

- Word-style ribbon with Home, Insert, Layout and Design tabs.
- Undo/redo, bold, italic, underline, subscript and superscript.
- Font family, font size, text colour and highlighting.
- Bullets, numbering, alignment, indentation and line spacing.
- Reusable Word-like styles: Normal, No Spacing, Title, Subtitle, Heading 1–3, Quote and Intense Quote.
- Tables with row/column tools, images, links, horizontal rules and page breaks.
- Page size, orientation and margin controls.
- Seven document themes.
- Twelve templates: blank document, formal letter, business letter, memo, meeting minutes, report, proposal, policy, contract, invoice, certificate and résumé.
- Drag-and-drop fields for signature, initials, signing date, printed name, title/capacity, general text and checkbox consent.
- Field properties for label, assigned signer, required state and width.
- A4/Letter paper canvas, zoom, word count, character count and field count.
- Autosave, revision checkpoints, view-only access and conflict detection.
- Sharing with permitted LoanHub users using view/edit access.
- Word download, PDF download, browser printing and publishing into the file library.

## Routes available to all supported user areas

```text
/company/documents
/borrower/documents
/superadmin/documents
/platform/documents
```

Each area also has an editor route at `/{area}/documents/{document_id}`.

## Local setup

```bash
cd apps/frontend
corepack enable
pnpm install --frozen-lockfile
```

Configure the API base URL in your existing frontend environment. For local development on the same PC, the project normally expects a value similar to:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
```

Start Next.js:

```bash
pnpm dev
```

## Validation

```bash
pnpm typecheck
pnpm lint
pnpm build
```

## Signature field usage

1. Open the **Insert** ribbon tab.
2. Drag a field from **Signature and fillable fields** onto the paper, or click it to insert at the cursor.
3. Select the field to edit its label, assigned signer, required state and width.
4. Drag the field by its handle to reposition it.
5. Save, export to Word/PDF or print. The field remains part of the revision and exported document.

## Deployment notes

- Deploy the backend migration before opening the new editor in production.
- Rebuild the Next.js image after changes to `NEXT_PUBLIC_*` values.
- Use HTTPS in production.
- Do not package `.next`, `node_modules`, `.env.local` or other machine-specific files in source distributions.
