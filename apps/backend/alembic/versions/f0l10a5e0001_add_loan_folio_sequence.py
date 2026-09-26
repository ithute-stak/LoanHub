"""add immutable loan folio sequence

Revision ID: f0l10a5e0001
Revises: a0o4q6s8t802
Create Date: 2026-09-26
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "f0l10a5e0001"
down_revision = "a0o4q6s8t802"
branch_labels = None
depends_on = None

_STOP_WORDS = {"pty", "ltd", "limited", "inc", "incorporated", "company", "co", "the"}


def _words(value: str | None) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", str(value or "").lower())


def _safe(value: str | None, fallback: str, limit: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
    return cleaned[:limit] or fallback


def _company_code(name: str | None) -> str:
    normalized = " ".join(_words(name))
    if normalized in {"batlokoa financial service", "batlokoa financial services"}:
        return "BFS"
    words = [word for word in _words(name) if word not in _STOP_WORDS]
    if not words:
        return "CMP"
    if len(words) == 1:
        return _safe(words[0][:3], "CMP", 5)
    return _safe("".join(word[0] for word in words), "CMP", 5)


def _group_code(explicit: str | None, group_name: str | None, employer_name: str | None) -> str:
    if explicit:
        return _safe(explicit, "GEN", 8)
    source = group_name or employer_name
    normalized = " ".join(_words(source))
    if normalized in {"lesotho defence force", "lesotho defense force"}:
        return "LDF"
    words = [word for word in _words(source) if word not in _STOP_WORDS]
    if not words:
        return "GEN"
    if len(words) == 1:
        return _safe(words[0][:4], "GEN", 8)
    return _safe("".join(word[0] for word in words), "GEN", 8)


def upgrade() -> None:
    op.add_column("client_company_loan", sa.Column("folio_number", sa.String(length=40), nullable=True))
    op.add_column("client_company_loan", sa.Column("folio_company_code", sa.String(length=8), nullable=True))
    op.add_column("client_company_loan", sa.Column("folio_group_code", sa.String(length=8), nullable=True))
    op.add_column("client_company_loan", sa.Column("folio_sequence", sa.Integer(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT l.id, l.company_id, c.name AS company_name,
               eg.code AS group_code, eg.name AS group_name, b.employer_name
        FROM client_company_loan AS l
        JOIN loan_companies AS c ON c.id = l.company_id
        JOIN borrowers AS b ON b.id = l.borrower_id
        LEFT JOIN employer_groups AS eg ON eg.id = b.employer_group_id
        ORDER BY l.company_id, l.created_at, l.id
    """)).mappings().all()

    counters: dict[tuple[str, str], int] = {}
    for row in rows:
        company_code = _company_code(row["company_name"])
        group_code = _group_code(row["group_code"], row["group_name"], row["employer_name"])
        key = (str(row["company_id"]), group_code)
        sequence = counters.get(key, 0) + 1
        counters[key] = sequence
        folio = f"{company_code}-{group_code}-{sequence:05d}"
        bind.execute(
            sa.text("""
                UPDATE client_company_loan
                SET folio_number = :folio,
                    folio_company_code = :company_code,
                    folio_group_code = :group_code,
                    folio_sequence = :sequence
                WHERE id = :loan_id
            """),
            {
                "loan_id": row["id"],
                "folio": folio,
                "company_code": company_code,
                "group_code": group_code,
                "sequence": sequence,
            },
        )

    op.alter_column("client_company_loan", "folio_number", existing_type=sa.String(length=40), nullable=False)
    op.alter_column("client_company_loan", "folio_company_code", existing_type=sa.String(length=8), nullable=False)
    op.alter_column("client_company_loan", "folio_group_code", existing_type=sa.String(length=8), nullable=False)
    op.alter_column("client_company_loan", "folio_sequence", existing_type=sa.Integer(), nullable=False)

    op.create_index("ix_client_company_loan_folio_number", "client_company_loan", ["folio_number"], unique=False)
    op.create_index("ix_client_company_loan_folio_group_code", "client_company_loan", ["folio_group_code"], unique=False)
    op.create_unique_constraint(
        "uq_client_loan_folio_sequence",
        "client_company_loan",
        ["company_id", "folio_group_code", "folio_sequence"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_client_loan_folio_sequence", "client_company_loan", type_="unique")
    op.drop_index("ix_client_company_loan_folio_group_code", table_name="client_company_loan")
    op.drop_index("ix_client_company_loan_folio_number", table_name="client_company_loan")
    op.drop_column("client_company_loan", "folio_sequence")
    op.drop_column("client_company_loan", "folio_group_code")
    op.drop_column("client_company_loan", "folio_company_code")
    op.drop_column("client_company_loan", "folio_number")
