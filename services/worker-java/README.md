# LoanHub Java event worker

Java handles enterprise-style event and batch work where the JVM is a strong fit.

Current bounded responsibilities:
- canonicalize outbound event payloads for parity-checked delivery;
- summarize event batches by type;
- expose health/readiness for the LoanHub runtime dashboard.

It is deliberately non-authoritative. Python remains the source of truth for
loan decisions, accounting, tenancy, Experian/CDAS mutation safety, and webhook
delivery state.
