# Accounts and login

Implemented 4 September 2026. These features work without flood-sensor hardware.

## What works

- Residents register in Flutter with name, email, password, phone, and barangay.
- The web command center accepts administrator and officer accounts. The resident mobile app accepts resident accounts.
- Users can edit their profile. Email/password changes through the profile endpoint require their current password.
- Administrators list, create, edit, deactivate, and reactivate accounts. They cannot deactivate or demote themselves. Public registration cannot assign a staff role.
- Account data persists in the backend database. Logout, deactivation, role changes, and password resets revoke the relevant sessions.
- The existing Figma layouts are retained. Web user management and both login flows now use the API instead of demo account state. Mobile profile information comes from the signed-in account.

Station monitoring, map artwork and flood alerts remain prototype features. Practice SOS and forecast availability now use their documented backend APIs. Authentication does not turn sample readings or practice requests into live emergency services.

## Start locally

Run commands from the indicated project subfolder. The existing Python environment has the account dependencies installed on this workstation. On a fresh machine, install `requirements-dev.txt` first.

### Create your first administrator in the browser

Once the API and web app are running using the commands below, open
<http://localhost:3000/register>, or choose **Create administrator account** on the
login screen. Enter your name, email, phone, barangay, password and confirmation.
The **Show passwords** control lets you check your input. Passwords require 12–128
characters. Local tests can use `admin@example.com`; no email verification is sent.
Successful registration signs you in to the dashboard automatically.

This is one-time local setup. Both the Next.js development server and the backend
must run locally; production web builds do not offer administrator registration.
FastAPI also requires `AGAPAY_ENVIRONMENT=development`,
`AGAPAY_LOCAL_ADMIN_SETUP_ENABLED=true`, a loopback peer and a localhost URL.
Keep development servers bound to `127.0.0.1`. The setup endpoint ignores forwarded
headers as proof of local access. Disabling the flag closes browser setup.

After setup, the form closes and the login link disappears. Create additional staff
through **Users → Add User**. An existing administrator, including an inactive one,
closes setup. A persistent database claim prevents simultaneous submissions from
creating multiple first administrators and prevents setup reopening after role
changes. Duplicate emails and invalid inputs do not consume the setup opportunity.
Resident registration continues through the mobile app with a different email.

### Optional terminal setup

In `agapay-backend`:

```powershell
.\.venv\Scripts\python.exe -m app.create_admin
```

Enter your administrator name, email, phone, barangay, and a password of 12–128 characters. Password entry is hidden: typing produces no visible characters, but Enter submits it. There is no built-in administrator password. The command shares the browser setup lock and refuses to overwrite an existing email or run after setup is complete. The CLI also remains available for initial production setup.

If the project has no Python environment yet:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### Start the API

In `agapay-backend`, keep this terminal running:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: <http://127.0.0.1:8000/docs>.

The default SQLite database is `agapay_dev.db` in this directory. Account/session and `administrator_setup` tables are added with SQLAlchemy `create_all`; existing station and telemetry rows are retained. This is an additive local-development change. Versioned database migrations remain necessary before shared deployment or future changes to existing columns.

### Start the web command center

In `agapay-web`:

```powershell
npm.cmd run dev
```

Open the URL printed by Next.js, normally <http://localhost:3000/login>. Choose **Create administrator account** for first setup, or sign in with an existing account. The sidebar identifies the real account. **Users** is administrator-only; **My Profile** is available to both staff roles.

Next.js communicates with `http://127.0.0.1:8000` by default. To change it, create `agapay-web/.env.local` with `AGAPAY_API_URL=https://your-api-host` and restart Next.js. This is a server-only setting, not a `NEXT_PUBLIC_` variable. Behind a reverse proxy, also set `AGAPAY_WEB_ORIGIN` to the exact public web origin used for mutation-origin checks.

### Start mobile

For a browser preview, in `agapay-mobile`:

```powershell
flutter pub get
flutter run -d chrome --web-port 8080 --dart-define=AGAPAY_API_URL=http://127.0.0.1:8000
```

The backend permits the browser preview origins `http://localhost:8080` and `http://127.0.0.1:8080`. Changing the preview port requires updating `AGAPAY_CORS_ORIGINS` in the backend environment and restarting it, for example:

```dotenv
AGAPAY_CORS_ORIGINS=["http://localhost:8080","http://127.0.0.1:8080"]
AGAPAY_SESSION_DAYS=7
```

For an Android emulator, the default API address is `http://10.0.2.2:8000`; the debug Android manifest permits local HTTP. A physical phone needs a reachable API address configured with `--dart-define=AGAPAY_API_URL=...`. Release native builds require HTTPS. Both the mobile web preview and Android debug APK build were verified. Native device execution, physical-device secure storage, and iOS execution still need device validation.

The Android artifact is `agapay-mobile/build/app/outputs/flutter-apk/app-debug.apk`. It uses the emulator API default. The project uses `flutter_secure_storage` 10.3.1 with the existing SDK 36 toolchain; version 11 requires SDK 37, which has an [upstream compatibility issue](https://github.com/juliansteenbakker/flutter_secure_storage/issues/1224) with the available stable tooling.

Create a resident account through **Register**. It should then appear under web **Users**. Updating the resident profile changes the same database record shown to the administrator.

## Account API contract

| Method/path | Access | Result |
| --- | --- | --- |
| `GET /api/auth/setup` | Local development | Reports whether first-administrator registration is available |
| `POST /api/auth/setup` | Local development, one-time, rate-limited | Creates the first administrator and returns a session |
| `POST /api/auth/register` | Public, rate-limited | Creates a resident and returns a session |
| `POST /api/auth/login` | Public, rate-limited | Accepts email, password, and audience `web` or `mobile` |
| `GET /api/auth/me` | Valid bearer session | Current account, without password/session secrets |
| `PATCH /api/auth/me` | Valid bearer session | Updates name, email, phone, barangay, or password |
| `POST /api/auth/logout` | Bearer session if present | Revokes that session; repeat logout is harmless |
| `GET /api/users` | Administrator | Account list |
| `POST /api/users` | Administrator | Creates an account with a selected role |
| `PATCH /api/users/{id}` | Administrator | Edits profile/role/status or resets password |

Registration accepts `name`, `email`, `password`, `phone`, and `barangay`; it rejects a supplied `role`. Login returns `access_token`, `token_type`, `expires_at`, and `user`. Account responses expose `id`, `name`, `email`, `phone`, `barangay`, `role`, `is_active`, `created_at`, and `updated_at`. Timestamps are UTC. Email addresses are normalized and uniquely indexed.

The web browser calls same-origin `/api/account/*` handlers. Next.js holds the backend session in an HttpOnly cookie; the token is never returned to browser JavaScript. Each protected backend action checks the current database role/status. Web page guards run at the page level as well as in the shared layout, and the Users API independently requires administrator access.

Passwords use Argon2 through `pwdlib`. Sessions use random 256-bit opaque tokens with only SHA-256 digests in the database and a default seven-day lifetime. This is an explicit implementation choice in place of the plan's earlier JWT suggestion: server-backed sessions provide immediate revocation without a signing-secret setup. Native Flutter uses platform secure storage; its browser preview uses the plugin's WebCrypto storage and requires localhost or HTTPS. Passwords are never saved by the application.

Login attempts are limited per normalized email and server-observed IP, with a separate registration limit. The limiter is bounded and per process; use a shared limiter at the service/gateway when deploying multiple workers. The app does not trust caller-supplied forwarding headers for these limits.

## Verification and remaining work

Verified during implementation:

- 11 backend tests: existing telemetry behavior plus account validation, hashing, role escalation rejection, duplicate email handling, profile persistence, password changes, expiry, logout, deactivation, administration, and throttling.
- 8 Flutter tests: API/storage behavior, login failure, registration/profile editing, and existing navigation/narrow-screen coverage.
- Next.js type checking and production build; Flutter analysis, web build, and Android debug APK build.
- Live HTTP integration between FastAPI and Next.js using an isolated `accounts_smoke.db`: origin rejection, protected pages, HttpOnly/Secure cookies, resident registration appearing in web user management, profile changes, deactivation, and logout revocation.
- Browser checks of web sign-in and profile saving, plus mobile registration, saved profile display, and session restoration after a browser reload.

The isolated test database contains fictional QA accounts; those credentials are not a bootstrap mechanism for the normal development database.

Browser registration adds tests for setup closure, existing inactive administrators,
production/remote rejection, invalid payloads, duplicate rollback, concurrent claims
and unchanged resident permissions. The full backend suite passes 57 tests.
The production Next.js build passes. A headless browser check against an isolated
database verifies the registration link, mismatched-password error, Show/Hide
controls, 360-pixel layout, origin rejection, automatic HttpOnly-cookie sign-in,
dashboard access, logout/login and closed registration after setup. No test
administrator was added to the normal development database.

Email verification, self-service email password recovery, MFA, deployed infrastructure, sensor/device authentication, database migrations, and live emergency integrations are separate work. The mobile password-recovery link currently directs residents to an administrator; it does not claim to send an email. Before a public rollout, replace the inherited placeholder policy/terms copy with the project's approved documents.

Implementation references: [FastAPI password hashing guidance](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [Flutter secure storage platform setup](https://pub.dev/packages/flutter_secure_storage). Next.js authentication and cookie behavior were checked against the installed Next.js documentation.
