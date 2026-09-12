# Shared Mailbox-DNS edge

LoanHub owns the shared VPS public HTTP/HTTPS edge through Caddy. Mailbox-DNS remains isolated from ports 80/443 and exposes its web applications through its internal `nginx` service.

The Caddy service is attached to the existing external Docker network `mailbox-dns_mailbox_dns` and proxies these Ithute hostnames to `nginx:80`:

- `panel.ithute.co.ls`
- `api.ithute.co.ls`
- `groupware.ithute.co.ls`

`ithute.co.ls` and `www.ithute.co.ls` redirect to the panel. `mail.ithute.co.ls` exists at the Caddy edge so a public certificate can be issued and renewed for the SMTP/IMAP hostname.

The external network is intentionally not created by LoanHub. Mailbox-DNS must already be deployed on the shared VPS; otherwise Docker Compose fails closed instead of silently exposing or misrouting the Ithute services.
