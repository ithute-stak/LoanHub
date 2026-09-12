from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MIGRATION = BACKEND / "alembic/versions/z9n3p5q7r800_loanhub_native_hrms_foundation.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hrms_migration_has_expected_revision_chain_and_tables():
    source = read(MIGRATION)
    assert 'revision: str = "z9n3p5q7r800"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = "y8m2n4p6q790"' in source
    for table in (
        "hr_departments",
        "hr_positions",
        "hr_shifts",
        "hr_attendance_events",
        "hr_leave_types",
        "hr_leave_requests",
        "hr_payroll_runs",
        "hr_payroll_entries",
        "hr_vacancies",
        "hr_candidates",
        "hr_training_programs",
        "hr_training_enrollments",
        "hr_assets",
        "hr_asset_assignments",
    ):
        assert f'"{table}"' in source


def test_hrms_migration_index_names_fit_postgresql_limit():
    tree = ast.parse(read(MIGRATION))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"create_index", "drop_index"}:
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        value = node.args[0].value
        if isinstance(value, str):
            names.append(value)
    assert names
    assert max(len(name.encode("utf-8")) for name in names) <= 63


def test_every_hrms_model_is_company_scoped():
    source = read(BACKEND / "database/models/hrms.py")
    model_blocks = re.split(r"\nclass ", source)[1:]
    assert len(model_blocks) == 14
    for block in model_blocks:
        class_name = block.split("(", 1)[0]
        assert "company_id = Column" in block, f"{class_name} is not company-scoped"


def test_hrms_router_registers_core_native_module_endpoints():
    source = read(BACKEND / "routers/hrms.py")
    assert 'APIRouter(prefix="/hr"' in source
    for route in (
        '"/dashboard"',
        '"/departments"',
        '"/positions"',
        '"/shifts"',
        '"/attendance/events"',
        '"/leave/types"',
        '"/leave/requests"',
        '"/payroll/runs"',
        '"/recruitment/vacancies"',
        '"/recruitment/candidates"',
        '"/training/programs"',
        '"/assets"',
        '"/self-service/summary"',
    ):
        assert route in source
    api_router = read(BACKEND / "api/v1/router.py")
    assert "hrms.router" in api_router


def test_hrms_frontend_is_native_in_company_navigation():
    shell = read(FRONTEND / "components/portal/portal-shell.tsx")
    page = read(FRONTEND / "app/(dashboard)/company/hr/page.tsx")
    workspace = read(FRONTEND / "components/hr/hrms-workspace.tsx")
    assert 'href: "/company/hr"' in shell
    assert "HRMSWorkspace" in page
    for module in (
        "Employee management",
        "Attendance management",
        "Leave management",
        "Payroll management",
        "Recruitment",
        "Performance & training",
        "Asset management",
        "Organisation structure",
    ):
        assert module in workspace
