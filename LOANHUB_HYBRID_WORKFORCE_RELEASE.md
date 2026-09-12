# LoanHub Hybrid Workforce & HR Module

This incremental release consolidates LoanHub staff access, employee records, native HRMS operations and performance management into one role-aware workforce module.

## Navigation

The previous separate sidebar entries are replaced by one expandable **Workforce & HR** group:

- Command centre
- People & access
- Employee records
- Performance

The group automatically opens on workforce routes, remembers the user's open/closed preference, works in desktop, collapsed and mobile navigation modes, and filters every child by the active company role.

## Command-centre improvements

- Hybrid four-layer workforce overview.
- Role-aware quick actions.
- URL-addressable HR tabs such as `/company/hr?tab=attendance`.
- Browser back/forward compatibility for tab navigation.
- Partial-load resilience: one unavailable HR endpoint no longer prevents all other HR areas from loading.
- Existing `/company/staff`, `/company/employees`, `/company/people` and `/company/performance` routes remain compatible.

## Database impact

No schema change and no Alembic migration are required. This patch is designed to be applied after the rebased native HRMS patch.
