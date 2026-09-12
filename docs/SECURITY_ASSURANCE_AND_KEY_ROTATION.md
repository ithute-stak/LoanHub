# Security assurance and key rotation

LoanHub release gates now include repository secret scanning, Bandit SAST, authorization/error-leakage DAST checks, authentication rate-limit verification, security-response headers, backend regression tests and a real Chromium browser/API login gate.

These automated controls are release evidence, not a substitute for an independent penetration test. Before a regulated or high-value production launch, an independent security assessor must test tenant isolation, authentication/session handling, privilege escalation, IDOR/BOLA, injection, upload handling, WebSockets, reverse proxy/TLS, denial-of-service controls and infrastructure configuration. Record the assessor, scope, date, findings, remediation commit and retest result. External penetration-test status remains **PENDING** until signed by the assessor.

## Key ownership and rotation

Production secrets must be supplied by the deployment secret store or environment and must never be committed. Keep JWT signing keys, `SECRET_KEY`, `FERNET_SECRET_KEY`, `CHAT_ENCRYPTION_KEY`, `FILE_ENCRYPTION_KEY`, payment-provider secrets and S3 credentials separate. Access should be restricted to the smallest operations group and logged by the infrastructure provider.

For JWT signing-key rotation, generate a new asymmetric key pair offline, deploy the new private/public pair in one controlled maintenance window, restart all API instances together, and force users to authenticate again because tokens signed by the retired key are intentionally invalidated. Keep a rollback copy of the previous pair only for the approved rollback window, then destroy it securely.

For data-encryption keys, do **not** simply replace a key while ciphertext still depends on it. Back up and verify the database/object store first, run a controlled re-encryption job that decrypts each record/object with the old key and encrypts it with the new key, verify checksums and sample reads, then remove the old key after the rollback window. If dual-key migration support is introduced later, document exact key versions and retirement dates.

Rotate credentials immediately after suspected exposure, staff access changes, provider compromise, or failed integrity controls. Planned production rotation should be rehearsed at least quarterly and performed at an interval approved by the lender's security policy. Every rotation must have an owner, ticket/change reference, start/end time, verification result and rollback record.

## Upload and object-storage security

Managed-file plaintext is MIME validated and, when enabled, scanned by ClamAV before encryption and storage. Production should set `MALWARE_SCAN_ENABLED=true` and `MALWARE_SCAN_FAIL_CLOSED=true`. The storage backend supports local disk for one-node deployments and S3-compatible object stores for MinIO/AWS-style scale-out. Application-level AES encryption remains in place before object storage; S3 server-side encryption is also requested.

For scale-out production set `FILE_STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION` and provider credentials. For MinIO also set `S3_ENDPOINT_URL` and normally `S3_ADDRESSING_STYLE=path`. Use a private bucket, disable public access, enable versioning/object-lock where business policy requires it, use lifecycle rules, replicate/back up to a separate failure domain, and rotate access keys independently of application encryption keys.
