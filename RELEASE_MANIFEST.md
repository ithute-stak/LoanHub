**LoanHub Final Engineered Release Manifest**  
**Product and developer identity**  
- Product: LoanHub — Lesotho Loan Marketplace  
- Product icon: brand/loanhub-app-icon.png  
- Product horizontal logo: brand/loanhub-horizontal-logo.png  
- Developer and maintenance partner: Ithute Solutions  
- Developer logo: brand/ithute-solutions-developer-logo.png  
**Final engineering additions.**  
- Platform-owner-only unhandled-error notifications  
- Privacy-safe ordinary-user error responses with request IDs  
- Audited, time-limited platform-owner role switching  
- Floating chat access, online/offline presence and last seen  
- Voice-note recording and authenticated playback  
- AES-GCM encryption at rest for chat text and managed files  
- Robust PDF, image, office and audio file handling  
- Midnight Africa/Maseru reconciliation and PDF/CSV generation  
- Platform, company and branch daily/weekly/monthly/annual reports  
- Light, dark and system themes  
- Live dashboards and removal of static demonstration routes  
- Privacy-safe password-recovery support requests  
- One Docker Compose production stack  
- GitHub Actions validation and Hostinger VPS deployment  
- README documentation in every source directory  
- 51-page role-by-role user and operations manual  
**Database**  
Current Alembic head: f1a9c4e7b620  
The migration graph is linear. Complete offline upgrade and downgrade SQL are included under docs/.  
**Validated inventory**  
- SQLAlchemy models/tables: 37 / 37  
- FastAPI router modules: 25  
- OpenAPI paths: 108  
- HTTP operations: 145  
- Frontend TypeScript/TSX implementation files: 265  
- Missing local frontend imports: 0  
- Manual pages: 51  
**Production limitations**  
- A live migration must still be tested against a backup/staging copy of the target PostgreSQL database.  
- Full frontend typecheck/lint/build is executed by the Dockerfile and GitHub Actions; it could not be repeated in the artifact environment without registry access.  
- Chat/file encryption is server-managed encryption at rest, not client-to-client end-to-end encryption.  
- Live M-Pesa/EcoCash settlement and certification still require official merchant onboarding and provider integration.  
