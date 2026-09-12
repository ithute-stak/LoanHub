from io import BytesIO

from PIL import Image, ImageDraw

from services.workspace_document_asset_service import extract_signature_image, normalize_logo_image
from services.workspace_document_service import default_document_html, signature_field_metadata


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_signature_image_background_is_removed_and_cropped():
    image = Image.new("RGB", (900, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.line((180, 220, 300, 140, 430, 230, 560, 120, 700, 205), fill="black", width=13)

    payload, width, height, metadata = extract_signature_image(_png(image))
    result = Image.open(BytesIO(payload)).convert("RGBA")

    assert result.format == "PNG" or payload.startswith(b"\x89PNG")
    assert width < 900
    assert height < 360
    assert result.getchannel("A").getbbox() is not None
    assert metadata["background_removed"] is True
    assert metadata["ink_coverage"] > 0


def test_logo_normalisation_outputs_png():
    image = Image.new("RGBA", (500, 200), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 40, 420, 160), fill=(20, 90, 160, 255))

    payload, width, height, metadata = normalize_logo_image(_png(image))

    assert payload.startswith(b"\x89PNG")
    assert width <= 500
    assert height <= 200
    assert metadata["normalised"] is True


def test_loan_agreement_template_is_editable_and_contains_signature_fields():
    html = default_document_html("loan_agreement", "Test Writer")
    fields = signature_field_metadata(html)

    assert "LOAN AGREEMENT" in html
    assert "CONDITIONS OF LOAN" in html
    assert "Early settlement" in html
    assert "Dispute resolution" in html
    assert len(fields) >= 2
    assert {field["field_type"] for field in fields.values()} <= {"signature", "initials", "date", "name", "title", "text", "checkbox"}


def test_expanded_template_catalogue_contains_cv_proposal_and_contract_variants():
    keys = [
        "executive_cv",
        "software_cv",
        "graduate_cv",
        "academic_cv",
        "skills_cv",
        "business_proposal",
        "technical_proposal",
        "tender_proposal",
        "funding_proposal",
        "partnership_proposal",
        "service_agreement",
        "employment_contract",
        "nda",
        "consultancy_agreement",
        "partnership_agreement",
    ]
    for key in keys:
        html = default_document_html(key, "Test Writer")
        assert html.strip()
        assert html != default_document_html("formal_letter", "Test Writer")


def test_private_signature_asset_helpers_never_expose_another_users_vault_asset():
    from types import SimpleNamespace
    from uuid import uuid4

    from fastapi import HTTPException

    from services.workspace_document_asset_service import (
        private_signature_asset_id,
        signature_asset_bytes_for_owner,
        signature_asset_is_owned_by,
    )

    owner_id = uuid4()
    other_id = uuid4()
    asset_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id,
        owner_user_id=owner_id,
        kind="signature",
        is_active=True,
        is_encrypted=False,
        image_data=b"private-signature",
    )
    row = SimpleNamespace(
        asset_id=asset_id,
        signer_user_id=owner_id,
        asset=asset,
    )

    assert signature_asset_is_owned_by(row, owner_id) is True
    assert private_signature_asset_id(row, owner_id) == asset_id
    assert signature_asset_bytes_for_owner(row, owner_id) == b"private-signature"

    assert signature_asset_is_owned_by(row, other_id) is False
    assert private_signature_asset_id(row, other_id) is None
    try:
        signature_asset_bytes_for_owner(row, other_id)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Another user must never receive signature-vault bytes")
