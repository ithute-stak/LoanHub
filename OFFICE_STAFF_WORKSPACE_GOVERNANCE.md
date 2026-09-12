# Office Staff Workspace Governance

This release turns LoanHub Office Workspace into a staff-aware document and spreadsheet filing system.

## Access model

- Normal staff work is private by default.
- A staff member sees their own work, work explicitly shared with them, and work deliberately marked **Company public**.
- Company owners have a read-only oversight view of every workspace item belonging to the active company.
- Owner oversight does not transfer ownership and does not automatically grant edit/delete/share rights over staff-owned work.
- Direct sharing supports **Can view** and **Can edit** permissions using the existing workspace collaborator model.

## Staff folders

- Every active company user receives a personal root folder named from their LoanHub display name when they use the Office Workspace.
- Existing unassigned personal work is filed into that personal folder on workspace load.
- New documents and spreadsheets are automatically filed into the creator's personal folder by the frontend workflow.
- Custom folders remain manageable only by their creator.
- The company owner can browse staff folders without silently moving or deleting another staff member's work.

## Documents

- Document folders expose **Tiles** and **List** views; the user's choice is remembered locally.
- The organizer includes **Company public** and **Shared with me** views.
- Owners receive an **Owner overview** and staff-grouped folder navigation.
- Sharing controls allow a document owner to keep work private, publish it within the company, or invite specific staff with view/edit access.

## Spreadsheets

- Spreadsheet Studio now uses the same folder governance as documents.
- Created and imported workbooks are filed into the staff member's personal folder.
- Spreadsheet folders support Tiles/List views and the same direct sharing/company-public workflow.
- Company-owner oversight can open and export staff workbooks but editing remains blocked unless the owner is explicitly granted edit access.

## Compatibility

- The existing `WorkspaceDocument` storage and collaborator tables are reused for both documents and spreadsheets.
- No new database migration is required for this upgrade.
- Existing Document Studio folder records and existing collaborators remain valid.
