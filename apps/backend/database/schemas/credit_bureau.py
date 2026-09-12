from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExperianCredentialsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=2, max_length=320)
    password: str = Field(min_length=1, max_length=1000)
    client_id: str = Field(min_length=2, max_length=500)
    client_secret: str = Field(min_length=1, max_length=1000)


class ExperianConfigurationUpdate(BaseModel):
    """Platform-owner Experian provider configuration.

    This schema intentionally contains the provider credentials and product API
    contract. Company-scoped endpoints never accept this schema.
    """

    model_config = ConfigDict(extra="forbid")

    environment: Literal["sandbox", "uat", "production"] = "sandbox"
    is_enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)
    credentials: ExperianCredentialsInput | None = None

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_legacy_environment(cls, value: Any) -> Any:
        return "sandbox" if str(value or "").strip().lower() == "manual" else value

    @model_validator(mode="after")
    def validate_product_configuration(self):
        endpoint = str(self.configuration.get("bureau_endpoint_path") or "").strip()
        if endpoint and (not endpoint.startswith("/") or endpoint.startswith("//") or "://" in endpoint or "\\" in endpoint):
            raise ValueError("Experian bureau endpoint must be a relative API path")
        request_template = self.configuration.get("request_template", {})
        response_mapping = self.configuration.get("response_mapping", {})
        if not isinstance(request_template, dict):
            raise ValueError("Experian request_template must be a JSON object")
        if not isinstance(response_mapping, dict):
            raise ValueError("Experian response_mapping must be a JSON object")
        return self


class ExperianCompanyUsageConfiguration(BaseModel):
    """Company lending policy for the shared platform Experian connection."""

    model_config = ConfigDict(extra="forbid")

    max_report_age_hours: int = Field(default=24, ge=1, le=720)
    require_before_affordability: bool = False
    include_bureau_commitments_in_affordability: bool = False
    bureau_debt_mode: Literal["max", "bureau_only", "declared_plus_bureau"] = "max"
    decline_below_score: int | None = Field(default=None, ge=0, le=1000)
    refer_below_score: int | None = Field(default=None, ge=0, le=1000)
    block_defaults: bool = False
    require_identity_match: bool = False

    @model_validator(mode="after")
    def validate_score_bands(self):
        if self.decline_below_score is not None and self.refer_below_score is not None:
            if self.decline_below_score > self.refer_below_score:
                raise ValueError("decline_below_score cannot be greater than refer_below_score")
        return self


class ExperianCompanySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool = False
    configuration: ExperianCompanyUsageConfiguration = Field(default_factory=ExperianCompanyUsageConfiguration)


class ExperianConnectionTestResult(BaseModel):
    provider: Literal["experian"] = "experian"
    environment: str
    host: str
    status: Literal["connected"] = "connected"
    token_type: str | None = None
    expires_in: int | None = None


class ExperianEnquiryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_confirmed: bool
    consent_method: Literal["written", "electronic", "recorded", "other"]
    consent_reference: str | None = Field(default=None, max_length=200)
    permissible_purpose: Literal["credit_application"] = "credit_application"

    @field_validator("consent_confirmed")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Borrower consent must be confirmed before a bureau enquiry")
        return value


class ExperianConfigurationPreview(BaseModel):
    provider: Literal["experian"] = "experian"
    environment: str
    is_enabled: bool
    has_credentials: bool
    last_test_status: str | None
    last_tested_at: Any | None
    configuration: dict[str, Any]


class CreditBureauEnquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    branch_id: str | None
    borrower_id: str
    application_id: str
    provider: str
    enquiry_type: str
    permissible_purpose: str
    consent_confirmed: bool
    consent_method: str | None
    consent_reference: str | None
    consent_captured_at: Any | None
    status: str
    provider_reference: str | None
    requested_at: Any
    completed_at: Any | None
    score: int | None
    risk_band: str | None
    identity_match: bool | None
    open_accounts_count: int
    defaults_count: int
    judgments_count: int
    collections_count: int
    recent_enquiries_count: int
    monthly_commitments: float
    total_balance: float
    normalized_result: dict[str, Any]
    error_code: str | None
    error_message: str | None
    requested_by_user_id: str | None


class CreditBureauDecisionContext(BaseModel):
    application_id: str
    declared_monthly_debt: float
    bureau_monthly_commitments: float | None
    bureau_total_balance: float | None
    variance: float | None
    score: int | None
    risk_band: str | None
    defaults_count: int | None
    latest_enquiry_id: str | None
    latest_enquiry_status: str | None
