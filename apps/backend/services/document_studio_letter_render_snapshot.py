"""Canonical snapshot of Document Studio fields that influence letter PDF output.

This fingerprints document-controlled rendering inputs. It does not cover
external branding files, active signature assets, installed fonts or the
rendering implementation; an actual trusted issuer must attest those too.
"""
from __future__ import annotations

from hashlib import sha256
from json import dumps
from uuid import UUID


PDF_SOURCE_FIELDS = (
    "id", "company_id", "template_key", "version", "title", "reference",
    "content_html", "page_size", "orientation",
    "margin_top_mm", "margin_right_mm", "margin_bottom_mm", "margin_left_mm",
    "style_key", "default_font_family", "default_font_size_pt",
    "default_line_height_percent", "include_brand_header", "include_footer",
    "is_confidential", "brand_logo_asset_id", "cover_page_enabled",
    "cover_page", "address_blocks", "status", "finalized_at", "is_deleted",
    "owner_user_id",
)


def _canonical(value):
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise PermissionError("Non-canonical letter rendering input")
        return {key: _canonical(item) for key, item in value.items()}
    raise PermissionError("Unsupported letter rendering input")


def letter_render_snapshot_sha256(document) -> str:
    """Strict fingerprint, not an approval or an exact final-PDF digest."""
    snapshot = {field: _canonical(getattr(document, field, None))
                for field in PDF_SOURCE_FIELDS}
    if (not isinstance(snapshot["id"], str)
            or not isinstance(snapshot["company_id"], str)
            or not isinstance(snapshot["content_html"], str)
            or not isinstance(snapshot["template_key"], str)):
        raise PermissionError("Incomplete persisted letter rendering snapshot")
    encoded = dumps(snapshot, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()
