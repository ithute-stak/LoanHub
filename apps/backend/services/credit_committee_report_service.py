from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from database.models.company import LoanCompany
from database.models.credit_committee import CreditCommitteeCase
from services.credit_committee_service import case_payload
from services.pdf_design_system import (
    BORDER,
    NAVY,
    DocumentContext,
    build_document,
    document_styles,
    generated_timestamp,
    hero_block,
    metric_grid,
    money_text,
    section,
)


def _text(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _list_paragraph(items: list[Any], style) -> Paragraph:
    values = [str(item).strip() for item in items if str(item).strip()]
    return Paragraph("<br/>".join(f"• {value}" for value in values) if values else "—", style)


def build_credit_committee_pdf(db: Session, case: CreditCommitteeCase) -> bytes:
    payload = case_payload(db, case, include_events=True)
    company = db.get(LoanCompany, case.company_id)
    assessment = payload.get("latest_assessment") or {}
    evidence = payload.get("evidence_snapshot") or {}
    affordability = evidence.get("affordability") or {}
    bureau = evidence.get("credit_bureau") or {}
    kyc = evidence.get("kyc") or {}
    employment = evidence.get("employment") or {}
    rules = evidence.get("rules_engine") or {}
    vote_summary = payload.get("vote_summary") or {}
    styles = document_styles()
    story: list[Any] = []

    story.extend(hero_block(
        "Credit Committee Credit Memo",
        f"{payload.get('borrower_name')} · application {payload.get('application_reference')}. Human underwriting and committee evidence for the lending decision.",
        payload.get("case_reference") or "Credit Committee",
        status=payload.get("final_decision") or payload.get("status") or "underwriting",
        styles=styles,
    ))
    story.append(metric_grid([
        ("Requested", money_text(payload.get("requested_amount") or 0), f"{payload.get('term_count') or 0} term(s)", "blue"),
        ("Proposed", money_text(assessment.get("proposed_amount") or 0), f"Installment {money_text(assessment.get('proposed_installment') or 0)}", "teal"),
        ("Risk grade", _text(assessment.get("risk_grade")).upper(), f"Analyst recommendation: {_text(assessment.get('recommendation')).replace('_', ' ').title()}", "amber"),
        ("Committee", _text(payload.get("final_decision") or payload.get("status")).replace("_", " ").title(), f"{vote_summary.get('decisive_vote_count', 0)} decisive vote(s)", "green" if payload.get("final_decision") in {"approved", "conditionally_approved"} else "red" if payload.get("final_decision") == "rejected" else "blue"),
    ], columns=4, styles=styles))

    story.extend(section(
        "Application and affordability evidence",
        "The memo preserves the evidence snapshot used by the analyst. Automated rules are supporting evidence only; the final committee decision remains separately recorded.",
        styles=styles,
    ))
    evidence_table = Table([
        ["Borrower", payload.get("borrower_name"), "Application", payload.get("application_reference")],
        ["Requested amount", money_text(payload.get("requested_amount") or 0), "Application type", _text(payload.get("application_type")).replace("_", " ").title()],
        ["Verified income", money_text(affordability.get("verified_income") or 0), "Household expenses", money_text(affordability.get("household_expenses") or 0)],
        ["Existing debt installments", money_text(affordability.get("existing_debt_installments") or 0), "DTI", f"{_text(affordability.get('dti_percent'))}%"],
        ["Affordability result", _text(affordability.get("decision")).replace("_", " ").title(), "Headroom", money_text(affordability.get("affordability_headroom") or 0)],
        ["Credit score", _text(bureau.get("score")), "Bureau risk grade", _text(bureau.get("risk_grade"))],
        ["KYC status", _text(kyc.get("status")).replace("_", " ").title(), "Employment verification", _text(employment.get("verification_status")).replace("_", " ").title()],
        ["Rules-engine result", _text(rules.get("decision")).replace("_", " ").title(), "Rules score", _text(rules.get("score"))],
    ], colWidths=[38*mm, 47*mm, 38*mm, 47*mm])
    evidence_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F8FB")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F6F8FB")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.1),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(evidence_table)
    story.append(Spacer(1, 4 * mm))

    story.extend(section("Analyst credit memo", "Versioned underwriting judgement submitted to the committee.", styles=styles))
    if assessment:
        memo = Table([
            ["Revision", assessment.get("revision"), "Recommendation", _text(assessment.get("recommendation")).replace("_", " ").title()],
            ["Risk grade", _text(assessment.get("risk_grade")).upper(), "Risk score", _text(assessment.get("risk_score"))],
            ["Proposed amount", money_text(assessment.get("proposed_amount") or 0), "Proposed installment", money_text(assessment.get("proposed_installment") or 0)],
            ["Rationale", Paragraph(_text(assessment.get("rationale")), styles["body_small"]), "Exceptions", _list_paragraph(assessment.get("exceptions") or [], styles["body_small"])],
            ["Strengths", _list_paragraph(assessment.get("strengths") or [], styles["body_small"]), "Weaknesses", _list_paragraph(assessment.get("weaknesses") or [], styles["body_small"])],
            ["Mitigants", _list_paragraph(assessment.get("mitigants") or [], styles["body_small"]), "Proposed conditions", _list_paragraph([item.get("title") if isinstance(item, dict) else item for item in assessment.get("proposed_conditions") or []], styles["body_small"])],
        ], colWidths=[31*mm, 54*mm, 31*mm, 54*mm])
        memo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F8FB")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F6F8FB")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(memo)
    else:
        story.append(Paragraph("No analyst credit memo has been submitted.", styles["body_small"]))
    story.append(Spacer(1, 4 * mm))

    story.extend(section("Committee votes", "Maker-checker controls keep the analyst separate from committee voting unless governance is explicitly changed and audited.", styles=styles))
    vote_rows: list[list[Any]] = [["Member", "Role", "Vote", "Rationale", "Conditions"]]
    for vote in payload.get("votes") or []:
        vote_rows.append([
            vote.get("user_id") or "—",
            _text(vote.get("role")).replace("_", " ").title(),
            _text(vote.get("decision")).replace("_", " ").title(),
            Paragraph(_text(vote.get("rationale")), styles["body_small"]),
            _list_paragraph([item.get("title") if isinstance(item, dict) else item for item in vote.get("conditions") or []], styles["body_small"]),
        ])
    votes_table = Table(vote_rows, colWidths=[32*mm, 30*mm, 30*mm, 48*mm, 34*mm], repeatRows=1)
    votes_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 6.8),
        ("FONTSIZE", (0, 1), (-1, -1), 6.3),
        ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(votes_table)
    story.append(Spacer(1, 4 * mm))

    story.extend(section("Final decision and conditions", "The final committee result, any documented override, and condition evidence are retained with the application audit trail.", styles=styles))
    final_table = Table([
        ["Computed outcome", _text(vote_summary.get("computed_outcome")).replace("_", " ").title(), "Final decision", _text(payload.get("final_decision")).replace("_", " ").title()],
        ["Quorum", "Met" if vote_summary.get("quorum_met") else "Not met", "Approval ratio", f"{vote_summary.get('approval_ratio_percent', 0)}%"],
        ["Override used", "Yes" if payload.get("override_used") else "No", "Override reason", payload.get("override_reason") or "—"],
        ["Decision reason", Paragraph(_text(payload.get("final_decision_reason")), styles["body_small"]), "Finalised at", _text(payload.get("final_decided_at"))],
    ], colWidths=[31*mm, 54*mm, 31*mm, 54*mm])
    final_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F8FB")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F6F8FB")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(final_table)
    story.append(Spacer(1, 3 * mm))

    conditions = payload.get("conditions") or []
    if conditions:
        condition_rows: list[list[Any]] = [["Type", "Condition", "Status", "Evidence / waiver"]]
        for item in conditions:
            condition_rows.append([
                _text(item.get("condition_type")).replace("_", " ").title(),
                Paragraph(f"<b>{_text(item.get('title'))}</b><br/>{_text(item.get('description'))}", styles["body_small"]),
                _text(item.get("status")).title(),
                Paragraph(_text(item.get("evidence_note") or item.get("waiver_reason")), styles["body_small"]),
            ])
        condition_table = Table(condition_rows, colWidths=[34*mm, 70*mm, 25*mm, 45*mm], repeatRows=1)
        condition_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.6),
            ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(condition_table)

    story.append(Spacer(1, 4 * mm))
    story.extend(section("Audit trail", "Key committee events are retained as an append-only operating record.", styles=styles))
    event_rows: list[list[Any]] = [["When", "Event", "Actor", "Details"]]
    for event in payload.get("events") or []:
        details = event.get("payload") or {}
        event_rows.append([
            _text(event.get("created_at")),
            _text(event.get("event_type")).replace("_", " ").title(),
            event.get("actor_user_id") or "System",
            Paragraph(_text(details), styles["body_small"]),
        ])
    audit = Table(event_rows, colWidths=[38*mm, 38*mm, 40*mm, 58*mm], repeatRows=1)
    audit.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.1),
        ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(audit)

    return build_document(
        story=story,
        context=DocumentContext(
            db=db,
            company=company,
            title="Credit Committee Credit Memo",
            reference=case.case_reference,
            footer_note=generated_timestamp(),
            confidential=True,
        ),
        title=f"LoanHub Credit Committee Credit Memo - {case.case_reference}",
        subject="Underwriting evidence, committee votes, decision conditions and audit trail",
    )
