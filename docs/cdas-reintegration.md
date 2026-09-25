# CDAS reintegration branch

This branch intentionally contains only the CDAS authentication/configuration foundation.

Preserved:
- encrypted company-scoped CDAS credentials
- test/live endpoint validation
- `POST /api/security/login` authentication
- authentication connection test
- historical database models and Alembic migrations for migration safety

Removed from runtime until rebuilt and tested:
- employee lookup and affordability
- deduction reads/writes and lifecycle
- documents/output files/statements
- roster sync and all CDAS schedulers
- booking, bulk, analytics, intelligence, forecasting, monitoring and automation
- CDAS operational frontend pages

Do not merge this branch into production until the clean integration is rebuilt and UAT-approved.
