from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from PIL import Image, ImageEnhance, ImageOps, ImageStat
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.workspace_document import (
    WorkspaceDocument,
    WorkspaceDocumentAsset,
    WorkspaceDocumentSignature,
)
from services.crypto_service import decrypt_file_bytes, encrypt_file_bytes


MAX_SOURCE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_LOGO_EDGE = 1800
MAX_SIGNATURE_EDGE = 1600


def _open_image(payload: bytes) -> Image.Image:
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded image is empty")
    if len(payload) > MAX_SOURCE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Document images must be 8 MB or smaller")
    try:
        image = Image.open(BytesIO(payload))
        image.load()
        return ImageOps.exif_transpose(image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a supported image") from exc


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def normalize_logo_image(payload: bytes) -> tuple[bytes, int, int, dict[str, Any]]:
    image = _open_image(payload).convert("RGBA")
    image.thumbnail((MAX_LOGO_EDGE, MAX_LOGO_EDGE), Image.Resampling.LANCZOS)
    # Crop fully transparent whitespace but preserve normal white backgrounds.
    if image.getbbox():
        alpha_bbox = image.getchannel("A").getbbox()
        if alpha_bbox:
            image = image.crop(alpha_bbox)
    data = _png_bytes(image)
    return data, image.width, image.height, {"normalised": True, "format": "png"}


def extract_signature_image(payload: bytes) -> tuple[bytes, int, int, dict[str, Any]]:
    """Extract handwriting/ink from a photographed or scanned signature.

    The operation does not attempt biometric verification. It only removes the
    paper/background, crops surrounding whitespace and stores a transparent PNG
    that can be reused on authorised documents.
    """
    source = _open_image(payload).convert("RGB")
    source.thumbnail((MAX_SIGNATURE_EDGE, MAX_SIGNATURE_EDGE), Image.Resampling.LANCZOS)

    # Flatten lighting a little before estimating the paper colour from the border.
    gray = ImageOps.grayscale(source)
    gray = ImageEnhance.Contrast(gray).enhance(1.2)
    border_width = max(2, min(gray.size) // 35)
    edge_images = [
        gray.crop((0, 0, gray.width, border_width)),
        gray.crop((0, gray.height - border_width, gray.width, gray.height)),
        gray.crop((0, border_width, border_width, gray.height - border_width)),
        gray.crop((gray.width - border_width, border_width, gray.width, gray.height - border_width)),
    ]
    weighted_sum = 0.0
    weighted_pixels = 0
    for edge in edge_images:
        pixels_count = max(1, edge.width * edge.height)
        weighted_sum += ImageStat.Stat(edge).mean[0] * pixels_count
        weighted_pixels += pixels_count
    border_mean = weighted_sum / max(1, weighted_pixels)
    paper = max(175.0, min(255.0, border_mean))

    # Alpha grows with darkness relative to the estimated paper background. A
    # 256-entry lookup table keeps this fast even for phone photographs.
    threshold = 16.0
    scale = 2.9
    alpha_table = [
        0 if paper - value <= threshold
        else max(0, min(255, int((paper - value - threshold) * scale)))
        for value in range(256)
    ]
    alpha = gray.point(alpha_table)

    bbox = alpha.getbbox()
    if not bbox:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No clear signature ink was detected. Use a darker signature on plain paper and try again.",
        )

    # Reject tiny marks that are likely dust/noise.
    crop_alpha = alpha.crop(bbox)
    alpha_values = (
        crop_alpha.get_flattened_data()
        if hasattr(crop_alpha, "get_flattened_data")
        else crop_alpha.getdata()
    )
    coverage = sum(alpha_values) / (255 * max(1, crop_alpha.width * crop_alpha.height))
    if crop_alpha.width < 30 or crop_alpha.height < 8 or coverage < 0.008:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The signature is too faint or too small to extract reliably.",
        )

    rgba = source.convert("RGBA")
    rgba.putalpha(alpha)
    rgba = rgba.crop(bbox)

    # Add transparent breathing room so the signature never touches a field edge.
    padding = max(8, int(max(rgba.size) * 0.025))
    padded = Image.new("RGBA", (rgba.width + padding * 2, rgba.height + padding * 2), (255, 255, 255, 0))
    padded.alpha_composite(rgba, (padding, padding))
    data = _png_bytes(padded)
    return data, padded.width, padded.height, {
        "background_removed": True,
        "format": "png",
        "paper_luminance": round(paper, 2),
        "ink_coverage": round(float(coverage), 5),
    }


def image_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def default_asset(
    db: Session,
    owner_user_id: UUID,
    kind: str,
) -> WorkspaceDocumentAsset | None:
    return (
        db.query(WorkspaceDocumentAsset)
        .filter(
            WorkspaceDocumentAsset.owner_user_id == owner_user_id,
            WorkspaceDocumentAsset.kind == kind,
            WorkspaceDocumentAsset.is_default.is_(True),
            WorkspaceDocumentAsset.is_active.is_(True),
        )
        .order_by(WorkspaceDocumentAsset.updated_at.desc())
        .first()
    )


def resolved_brand_asset(db: Session, document: WorkspaceDocument) -> WorkspaceDocumentAsset | None:
    """Resolve the explicit or default logo for a workspace document.

    Older documents/test fixtures may predate brand_logo_asset_id and
    owner_user_id. Treat those optional branding fields as absent rather than
    failing an otherwise valid PDF/DOCX export.
    """
    brand_logo_asset_id = getattr(document, "brand_logo_asset_id", None)
    if brand_logo_asset_id:
        asset = db.get(WorkspaceDocumentAsset, brand_logo_asset_id)
        if asset and asset.is_active and asset.kind == "logo":
            return asset

    owner_user_id = getattr(document, "owner_user_id", None)
    if owner_user_id is None:
        return None
    return default_asset(db, owner_user_id, "logo")


def active_signatures(db: Session, document_id: UUID) -> dict[str, WorkspaceDocumentSignature]:
    rows = (
        db.query(WorkspaceDocumentSignature)
        .filter(
            WorkspaceDocumentSignature.document_id == document_id,
            WorkspaceDocumentSignature.revoked_at.is_(None),
        )
        .all()
    )
    return {row.field_id: row for row in rows}


def canonical_document_hash(document: WorkspaceDocument) -> str:
    payload = {
        "document_id": str(document.id),
        "reference": document.reference,
        "version": document.version,
        "title": document.title,
        "content_html": document.content_html or "",
        "cover_page": document.cover_page or {},
        "address_blocks": document.address_blocks or [],
        "style_key": document.style_key,
        "page_size": document.page_size,
        "orientation": document.orientation,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def protect_asset_bytes(
    content: bytes,
    *,
    force_encrypt: bool = False,
) -> tuple[bytes, bool, str | None, str | None]:
    """Protect reusable document assets before persistence.

    Handwritten signatures are always encrypted at rest, even when general
    managed-file encryption is disabled. Logos continue to respect the global
    FILE_ENCRYPTION_ENABLED setting.
    """
    if not force_encrypt and not settings.FILE_ENCRYPTION_ENABLED:
        return content, False, None, None
    encrypted, nonce, version = encrypt_file_bytes(content)
    return encrypted, True, nonce, version


def signature_asset_is_owned_by(
    signature: WorkspaceDocumentSignature,
    user_id: UUID,
) -> bool:
    """Return True only when the requesting user owns the vault asset.

    This deliberately does not grant access to document owners, company admins,
    platform admins or collaborators. A stored handwritten signature belongs
    exclusively to the user who uploaded and applied it.
    """
    asset = signature.asset
    return bool(
        signature.asset_id
        and signature.signer_user_id == user_id
        and asset is not None
        and asset.id == signature.asset_id
        and asset.owner_user_id == user_id
        and asset.kind == "signature"
        and asset.is_active
    )


def private_signature_asset_id(
    signature: WorkspaceDocumentSignature,
    viewer_user_id: UUID,
) -> UUID | None:
    """Expose a signature-vault asset id only to its owner."""
    if not signature_asset_is_owned_by(signature, viewer_user_id):
        return None
    return signature.asset_id


def signature_asset_bytes_for_owner(
    signature: WorkspaceDocumentSignature,
    viewer_user_id: UUID,
) -> bytes:
    """Return decrypted signature bytes only to the vault owner.

    A 404 is used instead of 403 so callers cannot probe whether another user's
    private signature exists.
    """
    if not signature_asset_is_owned_by(signature, viewer_user_id):
        raise HTTPException(status_code=404, detail="Signature image not found")
    return asset_image_bytes(signature.asset)


def asset_image_bytes(asset: WorkspaceDocumentAsset) -> bytes:
    if not getattr(asset, "is_encrypted", False):
        return asset.image_data
    try:
        return decrypt_file_bytes(
            asset.image_data,
            getattr(asset, "encryption_nonce", None),
            getattr(asset, "encryption_version", None),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored document asset integrity verification failed",
        ) from exc
