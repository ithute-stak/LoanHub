# Office Workspace UI Orientation

This patch reorganises the combined Document/Spreadsheet workspace after reviewing the production screencast from 2026-08-08.

## Problem observed

The page rendered spreadsheet creation, document folders, a second Document Studio hero, the template gallery, and another document library as one long continuous page. This made the workflow feel duplicated and visually unstructured.

## New information architecture

- One Office Workspace header.
- Primary switch: **Documents** or **Spreadsheets**.
- Documents open by default.
- Document workspace has two focused views:
  - **Organize files** — folders, Word/PDF imports, document movement.
  - **Create & browse** — templates, shared documents, editor access.
- Spreadsheet templates/import are visible only while the Spreadsheet workspace is selected.
- The redundant embedded Document Studio hero is hidden inside the Create & browse view so the page has one clear title hierarchy.
- Controls remain responsive and stack naturally on small screens.

## Behaviour preserved

- Word/PDF import and folder management.
- Document templates, document browsing and editor navigation.
- Excel/CSV import.
- Spreadsheet templates and workbook creation.
- Existing visibility rules for company, borrower, platform and super-admin workspaces.
