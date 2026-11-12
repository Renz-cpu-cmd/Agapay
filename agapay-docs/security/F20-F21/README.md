# F20–F21 identity and mutation contracts

Implemented October 22, 2026. [Verification results](RESULTS.md) distinguish local software evidence from deployment acceptance. The original audit is unchanged. These additions build on the migrations and operational contracts for F01–F19; F16 physical commissioning remains pending.

## Account recovery and invitations

`GET /api/auth/capabilities` reports whether email recovery, invitations and authenticator setup are configured. Unconfigured email actions show an unavailable explanation in web and mobile; Google sign-in is hidden. Configuration alone is not proof of provider delivery.

- `POST /api/auth/recovery/request` accepts email and purpose `password_reset` or `verify_email`. Eligible and unknown accounts receive the same public response. Delivery is queued, without SMTP network activity in the request. This is not a measured constant-time guarantee.
- Recovery and verification codes expire after 30 minutes. Resending invalidates the previous code for that account and purpose. Tokens have 256 bits of randomness, are stored by hash, and are bound to the account email and version. Completion claims them atomically once.
- `POST /api/auth/recovery/complete` accepts the emailed token and, for reset/invitation, a new password. It never signs the person in automatically. Password recovery verifies contact ownership and deliberately revokes all API sessions and push authorizations. Existing MFA remains required.
- Administrators create invitations through `POST /api/auth/invitations`, with the intended account fields, role and reason. Invitations expire after 24 hours. Acceptance verifies email possession before creating an account. Issuer role, activation and version must still match; changed authority invalidates the invitation. Production rejects direct creation of staff accounts with an administrator-selected password.
- Email links put tokens in a URL fragment, which the recovery page removes immediately. The page is no-index and no-referrer. Mobile supports pasting the email code. Do not place tokens in logs or support messages.

## Staff MFA and session management

Production requires MFA for administrators and officers. Development keeps an explicit opt-in setting, while an enrolled account always requires its factor. Mobile remains resident-only.

Password-only staff login returns a restricted, five-minute challenge, not an API bearer or web session cookie. An account without a factor must first verify its email, then prove authenticator possession. TOTP uses RFC 6238 with SHA-1, six digits and 30-second steps; a one-step clock tolerance and a persisted counter prevent reuse. Challenges permit five incorrect attempts and also share an account budget. Synchronize server time.

Enrollment encrypts the seed, issues ten single-use recovery codes displayed once, increments account version, and revokes earlier sessions. Rotating an existing factor requires the current password and a fresh existing factor or unused recovery code. Email password recovery cannot remove MFA. The web BFF places a verified bearer only in its HTTP-only cookie and returns the user and one-time recovery codes to the browser.

`GET /api/auth/security` exposes only the owner's non-secret session IDs, audience, expiry, MFA state and push device metadata. Revoke-session, revoke-device and revoke-all actions require explicit owner intent and an audit reason. Revoking a device also revokes its associated API session, preventing that session from immediately registering the device again. Natural session expiration remains distinct from deliberate push revocation. No provider token is returned. Lists are bounded to 100 entries each; revoke-all covers the entire account.

If both authenticator and recovery codes are lost, a deployment custodian may use `python -m app.identity_admin`. Inspection is the default. Applying recovery requires `--apply`, a verified active staff account, and `--email`, `--operator`, `--reason`, `--evidence`. Evidence should be a reviewed case reference, not identity-document contents or secrets. This offline tool clears factors, revokes sessions/push, increments version and records the operator. The password stays unchanged and staff must enroll a new factor on next login. Restrict shell and database custody; this is not a public recovery endpoint.

## Conflict protection and general audit

Accounts expose `version`. Profile and administrative PATCH requests must send `expected_version`; privileged account creation and edits require a reason. Account locking, version comparison, mutation and audit commit occur together. Two competing writes cannot silently replace each other.

A stale write returns HTTP 409 with `detail.message` and a sanitized `detail.current` account. Web and mobile discard stale form/password values and block writes until the person explicitly refreshes and reviews. They never automatically replay the mutation. Existing station, governance and preference revision contracts continue to apply.

The general audit joins account creation/editing, bootstrap, identity challenges/recovery, session issuance/revocation, station/configuration actions, governance and preferences. Events contain actor identity, subject, reason and allowlisted before/after values. Passwords, bearer/provider tokens, MFA seeds and recovery codes are excluded from structured snapshots. Avoid secrets in free-text reasons. Account histories remain available after identity changes because actor IDs are historical references.

`GET /api/auth/audit` is administrator-only, bounded and filterable by subject. There is no audit update/delete endpoint; ORM updates/deletes are rejected. These are application append-only protections, not protection against a database owner or arbitrary raw SQL. For production, separate migration-owner credentials from application credentials and grant the application SELECT/INSERT only on the audit table, including required identity-sequence privileges. SQLite requires restrictive file custody and an external immutable audit export if tamper resistance is required. Establish retention, access review and backup procedures before rollout.

## Shared abuse controls and proxy identity

Authentication budgets persist as hashed keys in the shared application database. Atomic SQLite/PostgreSQL upserts work across workers using that same database, survive process restart, and fail closed with 503 if protection storage fails. The table prunes expired entries and has a 100,000-key admission bound; production edge controls must also bound aggregate connections and requests. This is not a measured distributed load-capacity claim.

Login budgets are per account (10/15 minutes) and client/account pair (30/15 minutes), with the account failure budget cleared after a successful password check. Registration is per email, recovery is per email and client/email, invitations are per administrator, and MFA has durable per-challenge plus shared per-account limits. No broad login-IP quota combines all office users behind the Next.js proxy. Account endpoints also have a 16 KiB body budget. Tune front-door resource limits using office/shared-network traffic and monitor account-targeted lockout abuse.

Plain forwarded headers do not establish identity. To enable signed BFF identity:

1. Bind Next.js behind an owned reverse proxy and prevent public direct access to its internal listener. The edge must overwrite a dedicated client-address header with its socket-derived address, discarding caller values.
2. Set the server-only web `AGAPAY_TRUSTED_CLIENT_IP_HEADER` to that exact header. Leave it unset when the edge has not been configured.
3. Configure backend `AGAPAY_AUTH_TRUSTED_PROXY_PEERS` with the explicit BFF peer CIDR and a dedicated `AGAPAY_AUTH_PROXY_KEY` of at least 32 characters on backend and web. Never use `NEXT_PUBLIC_*` for secrets. A `/0` trust range is rejected.
4. The BFF signs canonical client IP, timestamp, method and backend path. Backend checks the socket peer, HMAC and 30-second timestamp tolerance. Invalid assertions fall back to socket identity. The production launcher disables automatic Uvicorn proxy-header interpretation.

Verify this chain at the deployed reverse proxy. Forwarding an arbitrary inbound header through a trusted BFF would undermine it. PostgreSQL multi-host behavior and the production reverse-proxy chain still require integration acceptance; local tests exercised SQLite and signed synthetic requests.

## Coordinated deployment

No deployment, live database migration or external delivery was performed during implementation. Use a maintenance window; old clients without versions will receive validation errors.

1. Preserve backups and account/session identifiers, stop writers and workers, and confirm the actual target database. Complete earlier station, ordering, governance and interval migrations first. Do not reset or reseed data.
2. For an existing installation, from `agapay-backend`, inspect the identity plan:

   ```powershell
   .venv-auth/Scripts/python.exe -m app.migrate_identity_security
   ```

   After reviewing the target and backup, apply with `--apply`. It adds columns/tables/indexes, backfills non-secret session IDs, and preserves accounts and existing bearer hashes. Existing schema gaps cause startup to stop with a migration message. Duplicate pre-existing unfinished invitations must be reviewed if the unique index cannot be created; do not delete evidence automatically. A fresh empty installation uses the offline bootstrap in step 4 to create the schema first; do not create foreign-key workflow tables before their account tables.
3. Review [the production environment template](../../../agapay-backend/deploy/identity.production.env.example). Set an explicit database, HTTPS public origin, CORS origins, SMTP sender/authentication, Fernet encryption key, staff MFA and deployment confirmation. Disable demo seeding, local web bootstrap and prediction previews. Existing `.env` and credentials were not changed. Back up the encryption key separately with restricted access; losing it makes encrypted seeds/mail unreadable. Key rotation needs a deliberate re-encryption procedure.
4. For a fresh installation only, bootstrap the first administrator with `python -m app.create_admin` in the reviewed environment. Passwords are prompted privately; setup is one-time. Start production only with an active administrator present. After the reviewed service and mail worker are available in steps 5–6, verify that administrator's email through the public recovery page, then complete restricted MFA enrollment on first login. Existing installations retain their accounts and use the same contact-verification/enrollment flow.
5. Deploy backend, web and mobile contracts together. Run production through `python -m app.serve_production` with `AGAPAY_ENVIRONMENT=production` explicitly set in the service environment. It validates configuration/schema/bootstrap and binds `127.0.0.1:8000` with two workers behind the reviewed edge. Use a process supervisor. SQLite workers must share one local database; multi-host deployments need the reviewed shared PostgreSQL database and driver.
6. Once sender delivery is authorized/configured, run a bounded mail-worker batch with `python -m app.identity_mail_worker --limit 20` under the same protected environment. Schedule the worker through the deployment supervisor. No SMTP endpoint is contacted by ordinary recovery requests.
7. Complete controlled acceptance: real mailbox delivery and expiry/reuse; authenticator and backup-code login; offline recovery evidence; two real editors; process-restart/worker budget consistency; proxy spoof rejection; native storage and sign-out behavior. Check that protected audit database privileges actually reject UPDATE/DELETE.

Mail transitions `PENDING → SENDING → SENT/UNKNOWN/SUPPRESSED`. Claims are atomic. Expired/consumed actions are suppressed. Any SMTP ambiguity becomes UNKNOWN; a crash may leave SENDING. Neither state is automatically replayed. Review provider evidence and request a new token rather than resetting an ambiguous row. A SENT row means the SMTP call accepted the message, not proof of inbox delivery. Version changes can invalidate a queued link before delivery; completion still rejects it safely.

Production activation remains pending SMTP credentials, deployed edge/DB controls and acceptance above. F20–F21 software completion does not assert field calibration, operational-authority approval or native/provider acceptance.

## References

Recovery and factor behavior follows the [OWASP recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [OWASP MFA guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html) and [RFC 6238](https://www.rfc-editor.org/info/rfc6238/). The explicit deployment trust boundary follows [FastAPI's proxy guidance](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).
