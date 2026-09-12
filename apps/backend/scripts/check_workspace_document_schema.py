#!/usr/bin/env python3
"""Verify that the live database can support Document Studio creation.

Run from apps/backend:
    python scripts/check_workspace_document_schema.py
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect

from database.session import engine


EXPECTED: dict[str, set[str]] = {
    "workspace_documents": {
        "id",
        "owner_user_id",
        "company_id",
        "branch_id",
        "last_edited_by_user_id",
        "reference",
        "title",
        "template_key",
        "content_json",
        "content_html",
        "plain_text",
        "visibility",
        "status",
        "version",
        "page_size",
        "orientation",
        "margin_top_mm",
        "margin_right_mm",
        "margin_bottom_mm",
        "margin_left_mm",
        "style_key",
        "default_font_family",
        "default_font_size_pt",
        "default_line_height_percent",
        "include_brand_header",
        "include_footer",
        "is_confidential",
        "brand_logo_asset_id",
        "cover_page_enabled",
        "cover_page",
        "address_blocks",
        "finalized_at",
        "is_deleted",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "workspace_document_collaborators": {
        "id",
        "document_id",
        "user_id",
        "invited_by_user_id",
        "permission",
        "created_at",
        "updated_at",
    },
    "workspace_document_assets": {
        "id",
        "owner_user_id",
        "company_id",
        "kind",
        "label",
        "original_filename",
        "mime_type",
        "image_data",
        "is_encrypted",
        "encryption_nonce",
        "encryption_version",
        "width_px",
        "height_px",
        "sha256",
        "is_default",
        "is_active",
        "processing_metadata",
        "created_at",
        "updated_at",
    },
    "workspace_document_signatures": {
        "id",
        "document_id",
        "field_id",
        "field_type",
        "signer_user_id",
        "signer_name",
        "method",
        "asset_id",
        "consent_text",
        "signed_at",
        "document_version",
        "document_hash",
        "verification_code",
        "ip_hash",
        "user_agent_hash",
        "revoked_at",
        "revoked_by_user_id",
        "created_at",
        "updated_at",
    },
    "workspace_document_revisions": {
        "id",
        "document_id",
        "version",
        "title",
        "content_json",
        "content_html",
        "plain_text",
        "created_by_user_id",
        "created_at",
        "updated_at",
    },
}


def main() -> int:
    inspector = inspect(engine)
    available_tables = set(inspector.get_table_names())
    failures: list[str] = []

    for table_name, expected_columns in EXPECTED.items():
        if table_name not in available_tables:
            failures.append(f"MISSING TABLE: {table_name}")
            continue

        actual_columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            failures.append(
                f"MISSING COLUMNS: {table_name}: {', '.join(missing_columns)}"
            )
        else:
            print(f"OK: {table_name} ({len(actual_columns)} columns)")

    if failures:
        print("\nDocument Studio schema is not ready:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        print(
            "\nRun: alembic upgrade head",
            file=sys.stderr,
        )
        return 1

    print("\nDocument Studio schema is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
