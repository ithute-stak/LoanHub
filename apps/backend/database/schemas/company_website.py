from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


WEBSITE_TEMPLATES = {"trust_community", "modern_finance"}
MAX_CUSTOM_SECTIONS = 12
BLOCKED_SECTION_KEYS = {"script", "javascript", "raw_html", "unsafe_html", "iframe"}


def _validate_section_value(value, *, depth: int = 0):
    if depth > 4:
        raise ValueError("Custom website sections are nested too deeply")
    if isinstance(value, str):
        if len(value) > 6000:
            raise ValueError("Custom website section text is too long")
        if "javascript:" in value.lower():
            raise ValueError("Unsafe javascript links are not allowed")
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        if len(value) > 30:
            raise ValueError("Custom website section lists are too large")
        return [_validate_section_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > 20:
            raise ValueError("Custom website sections contain too many fields")
        clean = {}
        for key, item in value.items():
            field_name = str(key).strip()
            if not field_name or len(field_name) > 80:
                raise ValueError("Custom website section field names must be 1-80 characters")
            if field_name.lower() in BLOCKED_SECTION_KEYS:
                raise ValueError(f"Custom website field '{field_name}' is not allowed")
            clean[field_name] = _validate_section_value(item, depth=depth + 1)
        return clean
    raise ValueError("Custom website sections contain an unsupported value")


class CompanyWebsiteUpdate(BaseModel):
    template_key: str | None = None
    headline: str | None = Field(default=None, min_length=1, max_length=180)
    subheadline: str | None = Field(default=None, max_length=1200)
    about: str | None = Field(default=None, max_length=6000)
    primary_color: str | None = Field(default=None, max_length=12)
    accent_color: str | None = Field(default=None, max_length=12)
    hero_badge: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=30)
    contact_email: str | None = Field(default=None, max_length=255)
    show_loan_products: bool | None = None
    show_account_cta: bool | None = None
    custom_sections: list[dict] | None = None

    @field_validator("template_key")
    @classmethod
    def validate_template(cls, value: str | None) -> str | None:
        if value is not None and value not in WEBSITE_TEMPLATES:
            raise ValueError("Unknown website template")
        return value

    @field_validator("primary_color", "accent_color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        if value is None:
            return value
        clean = value.strip()
        if len(clean) != 7 or not clean.startswith("#"):
            raise ValueError("Colours must use #RRGGBB format")
        try:
            int(clean[1:], 16)
        except ValueError as exc:
            raise ValueError("Colours must use #RRGGBB format") from exc
        return clean.upper()

    @field_validator("contact_phone", "contact_email")
    @classmethod
    def clean_contact(cls, value: str | None) -> str | None:
        if value is None:
            return value
        clean = value.strip()
        return clean or None

    @field_validator("custom_sections")
    @classmethod
    def validate_custom_sections(cls, value: list[dict] | None) -> list[dict] | None:
        if value is None:
            return value
        if len(value) > MAX_CUSTOM_SECTIONS:
            raise ValueError(f"A public website can contain at most {MAX_CUSTOM_SECTIONS} custom sections")
        return [_validate_section_value(section) for section in value]


class CompanyWebsitePublish(BaseModel):
    is_published: bool = True


class CompanyWebsiteRead(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    public_code: str
    template_key: str
    is_published: bool
    headline: str
    subheadline: str | None = None
    about: str | None = None
    primary_color: str
    accent_color: str
    hero_badge: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    show_loan_products: bool
    show_account_cta: bool
    custom_sections: list[dict]
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PublicLoanProductRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    min_amount: float
    max_amount: float
    min_term_months: int
    max_term_months: int
    interest_rate_percent: float
    processing_fee: float


class PublicCompanyWebsiteRead(BaseModel):
    public_code: str
    company_name: str
    registration_number: str | None = None
    license_number: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_address: str | None = None
    company_district: str | None = None
    template_key: str
    headline: str
    subheadline: str | None = None
    about: str | None = None
    primary_color: str
    accent_color: str
    hero_badge: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    show_loan_products: bool
    show_account_cta: bool
    custom_sections: list[dict]
    loan_products: list[PublicLoanProductRead]