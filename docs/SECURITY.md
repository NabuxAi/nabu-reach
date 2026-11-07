# Security and responsible use

This is a **local prototype**, not an Internet-facing messaging server. It deliberately has no live-send provider or credential management. It has no authentication and stores personal data unencrypted in SQLite. **Only run it on a trusted machine, bound to localhost.** The Docker sample binds the host port to 127.0.0.1 only.

Data categories: phone number, optional name, consent source and timestamp, account labels, draft messages. Store/database backups must be protected and removed according to applicable retention requirements. Delete the `data/` folder to remove all local prototype data when the application is stopped.

Controls implemented: parameterized SQL, explicit opt-in evidence, opt-out precedence on CSV imports, strict content-type and payload-size limits, CSV row cap, server-side placeholder validation, HTTP origin check on writes, security headers, no external JS, no cross-origin API responses, no real messaging endpoints.

Not implemented: users, authentication, authorization, tenant isolation, login sessions, secret storage, malware scanning, compliance automation, end-user privacy notices, data deletion UI, complete opt-out workflow from incoming WhatsApp messages, delivery receipts, production logging, backups, at-rest encryption, provider integration and production rate limits.

Do not use this application to bypass WhatsApp restrictions, automate unsolicited outreach, evade bans, or rotate accounts to avoid enforcement. Production marketing must use the sender's authorized service and documented recipient consent.

Report security issues privately to the maintainer through GitHub Security Advisories if the repository is made public. Never include actual phone numbers or credentials in public bug reports.
