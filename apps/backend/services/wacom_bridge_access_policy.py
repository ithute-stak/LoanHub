"""Authorization policy for a company-managed, multi-operator Wacom PC bridge.

Pure, fail-closed rules. The caller MUST verify the LoanHub session, company
membership, signed workstation challenge, and current server-side assignments
before supplying these facts. This policy grants bridge *access*, NEVER
permission to sign or reuse any stored handwritten image.
"""
from dataclasses import dataclass
from enum import Enum

from database.models.enums import UserRole


class BridgeAccess(str, Enum):
    DENY = "deny"
    COMPANY_SETUP = "company_setup"
    OPERATOR = "operator"


@dataclass(frozen=True)
class BridgeFacts:
    authenticated: bool
    user_active: bool
    password_action_required: bool
    company_active: bool
    company_membership_active: bool
    role: UserRole | None
    workstation_enrolled: bool
    workstation_active: bool
    workstation_proof_valid: bool
    operator_assignment_active: bool
    lending_permission_active: bool


def decide_bridge_access(facts: BridgeFacts) -> BridgeAccess:
    """Only active company owners/admins configure; authorized staff operate.

    An employee still has to present personal LoanHub credentials, possess
    an approved per-operator assignment, and prove workstation identity.
    Role and membership are always derived server-side, not from browser input.
    """
    if not all((
        facts.authenticated,
        facts.user_active,
        not facts.password_action_required,
        facts.company_active,
        facts.company_membership_active,
        facts.workstation_enrolled,
        facts.workstation_active,
        facts.workstation_proof_valid,
    )):
        return BridgeAccess.DENY

    if facts.role in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
        return BridgeAccess.COMPANY_SETUP

    if (
        facts.role in {
            UserRole.BRANCH_MANAGER,
            UserRole.LOAN_OFFICER,
            UserRole.CREDIT_ANALYST,
        }
        and facts.operator_assignment_active
        and facts.lending_permission_active
    ):
        return BridgeAccess.OPERATOR
    return BridgeAccess.DENY
