# UNIQUE SETU — React and FastAPI Application

This repository contains the React/Vite frontend and the FastAPI/MongoDB backend. The browser app uses the independent FastAPI API by default. The optional Base44 CLI workflow is documented at the end for Base44-specific development.

Independent FastAPI + MongoDB backend intended to connect to an existing React frontend.

## Important implementation notes

- MongoDB is the only application database. No SQL database is used.
- Service seed data includes the 21 service names and Marathi document requirements supplied for them. Run `python -m scripts.seed_services` to publish the catalog; populated service checklists are preserved.
- Authentication uses Argon2id, short-lived session-bound access JWTs, and opaque refresh tokens stored only as hashes. Refresh rotates and revokes the prior session; logout, account suspension, role changes, and admin revocation invalidate sessions. Cookies are HttpOnly, SameSite-configurable, and state-changing cookie requests require `X-CSRF-Token` matching the readable `csrf_token` cookie. Login throttling is MongoDB-backed per IP and phone number.
- Forgot/reset password endpoints deliberately do not issue a reset token because no verified SMS/email recovery provider is configured.
- Local private file storage is provided for development. Production can use an S3-compatible private bucket or Cloudinary authenticated assets; signed download URLs expire after five minutes. File content is checked with `python-magic`; malware scanning is not implemented.
- The readiness endpoint returns HTTP 503 if MongoDB cannot be pinged. Startup also fails if MongoDB is not configured or reachable.
- Customers can browse published services and track applications. Owners/admins can review and progress applications; staff can access assigned application data and documents without verification or rejection permissions.
- The local readiness endpoint currently confirms a MongoDB connection; live Cloudinary/S3 uploads and production deployment have not been verified.
- No production deployment has been performed or verified by this source package.

## Requirements

- Python 3.11, 3.12, or 3.13
- MongoDB Atlas or a local MongoDB instance
- A strong secret for `JWT_SECRET_KEY`

## Local setup (Windows PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set `MONGODB_URI`, `MONGODB_DATABASE`, and a newly generated `JWT_SECRET_KEY` of at least 32 characters. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Start local MongoDB with Docker if available:

```powershell
docker run --name unique-solutions-mongodb -p 27017:27017 -v unique-solutions-mongodb-data:/data/db -d mongo:7
```

For MongoDB Atlas:
1. Create a database user with a strong password and least privilege for `unique_solutions_db`.
2. Configure Network Access to allow only the deployment's outbound IP where possible. Avoid `0.0.0.0/0` except temporary testing.
3. URL-encode reserved characters in the MongoDB password.
4. Keep `.env` out of Git.

Start the API:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: http://127.0.0.1:8000/docs  
Liveness: http://127.0.0.1:8000/api/v1/health/live  
Readiness: http://127.0.0.1:8000/api/v1/health/ready

The application fails startup when MongoDB cannot be reached; this is intentional.

## Start the React frontend

From the project root in a second PowerShell window, start the frontend using the same `127.0.0.1` host configured for backend CORS:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The frontend defaults to `http://127.0.0.1:8000/api/v1`; set `VITE_API_BASE_URL` in `frontend/.env.local` only when using a different API URL. Run `python -m scripts.seed_services` from `backend/` to publish the 21 provided Marathi service checklists. Sign in with a mobile number and password, selecting the account type assigned to that account; the backend verifies the selected type. Public registration is mobile-number based and creates customer accounts only.

Customer accounts can browse services, create applications, upload documents, and track status. Owners can review applications and documents, set priority and due dates, assign staff, and maintain follow-up tasks. Staff can only read assigned applications and download or copy application data. Admins manage accounts and service publication.

## Bootstrap privileged users

Run from `backend/` with `backend/.env` configured:

```powershell
python -m scripts.create_admin
python -m scripts.create_owner
python -m scripts.seed_services
```

Privileged accounts are created through interactive scripts, not public registration. Owners can create staff accounts in their workspace; administrators can change account roles and statuses. Do not use real customer data in development.

## Tests

```powershell
pytest -q
```

The current suite includes authentication/session helpers, HTTPX authorization, request-schema, phone-normalization, rate-limit, storage-validation, readiness, seed, and status-transition tests. It does not replace integration/security tests against a disposable MongoDB database.

## API summary

All paths use `/api/v1`.

### Authentication
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `POST /auth/forgot-password`
- `POST /auth/reset-password` (501 until verified recovery provider is configured)
- `GET /auth/me`

Registration and login set HttpOnly access/refresh cookies and a readable CSRF cookie; tokens are not returned in JSON. Browser requests must use `credentials: "include"`; state-changing requests must copy `csrf_token` into `X-CSRF-Token`. In production set `COOKIE_SECURE=true`, exact `FRONTEND_ORIGINS`, and HTTPS. Cookie-based refresh also requires the CSRF header.

### Services
- `GET /services`
- `GET /services/{service_id}`
- `GET /services/categories` (visible catalogue sections)
- `POST /services/categories`, `PATCH /services/categories/{category_id}`, `DELETE /services/categories/{category_id}` (admin)
- `PUT /services/{service_id}/thumbnail` and `GET /services/{service_id}/thumbnail`
- `POST /services` (admin)
- `PATCH /services/{service_id}` (admin)
- `POST /services/{service_id}/publish` (admin)
- `POST /services/{service_id}/archive` (admin)

### Applications
- `POST /applications`
- `GET /applications`
- `GET /applications/{application_id}`
- `GET /applications/completed-documents?q=...&page=1&page_size=20` (owner/admin)
- `PATCH /applications/{application_id}`
- `POST /applications/{application_id}/submit`
- `POST /applications/{application_id}/assign` (owner/admin)
- `POST /applications/{application_id}/status`
- `GET /applications/{application_id}/history`
- `POST /applications/{application_id}/comments`
- `GET /applications/{application_id}/comments` (customer-visible comments only for customers)
- `PATCH /applications/{application_id}/owner-fields` (owner/admin)

Application status transitions are restricted. Government authority approval is distinct from shop completion.

### Documents
- `POST /applications/{application_id}/documents/upload-url`
- `POST /applications/{application_id}/documents/confirm` (multipart `upload_id` + `file` in local mode; JSON `upload_id` after signed S3 upload)
- `POST /applications/{application_id}/documents/physical-receipt`
- `GET /applications/{application_id}/documents`
- `GET /documents/released` (customer's shared owner-issued documents only)
- `GET /documents/{document_id}/download-url`
- `GET /documents/{document_id}/download`
- `POST /documents/{document_id}/review`
- `POST /documents/{document_id}/replacement-request`

Storage validates extension, size, and actual content with `python-magic`; it does not rely on the client MIME header. S3 uses a signed upload post; Cloudinary uploads pass through the backend and are stored as private authenticated assets. Both S3 and Cloudinary downloads use five-minute signed URLs after application authorization. Each new document records its provider; existing local/S3 records remain readable and are not migrated by changing providers. Malware scanning is not implemented. Local storage is for development only.

### Profile photos
- `PUT /auth/me/photo` (authenticated customer; multipart `file`, JPEG or PNG)

Profile photo replacements update the customer's own MongoDB user record and retain only file metadata in API responses. File bytes remain in the selected storage provider.

### Tasks
- `POST /tasks` (owner/admin)
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/complete`

### Notifications
- `GET /notifications`
- `GET /notifications/unread-count`
- `GET /notifications/unread-documents`
- `POST /notifications/{notification_id}/read`
- `POST /notifications/read-all`

### Owner and admin
- `GET /owner/users`
- `POST /owner/staff`
- `GET /owner/reports/summary`
- `GET /owner/audit-logs` (admin only)
- `PATCH /admin/users/{user_id}/status` (JSON body: `{"account_status":"suspended"}`)
- `PATCH /admin/users/{user_id}/role` (JSON body: `{"role":"staff"}`)
- `PATCH /admin/users/{user_id}/permissions` (JSON body: `{"permissions":["reports:read"]}`)
- `POST /admin/users/{user_id}/revoke-sessions`
- `GET /admin/health/storage`

## Example API requests

Register:
```json
{
  "full_name": "Test Customer",
  "mobile_number": "9876543210",
  "password": "ExamplePass123",
  "preferred_language": "mr"
}
```

Create application:
```json
{
  "service_id": "SERVICE_OBJECT_ID",
  "customer_notes": "Please help process this service."
}
```

Change status:
```json
{
  "status": "Received by Shop",
  "reason": "Documents received at the counter"
}
```

## MongoDB collections and indexes

Collections: `users`, `services`, `service_versions`, `applications`, `application_documents`, `document_upload_intents`, `application_status_history`, `application_tasks`, `notifications`, `audit_logs`, `sessions`, `rate_limits`, `application_comments`.

Indexes are created idempotently at startup:
- Unique normalized mobile number.
- Unique service code.
- Unique application number.
- Application/customer/staff/status lookup indexes.
- Notification recipient/read/time indexes and partial unique dedupe key.
- Audit time index.
- TTL indexes for sessions, rate limits, and upload intents.

## Frontend integration

Set frontend environment variable:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Example cookie-authenticated fetch:
```js
const API = import.meta.env.VITE_API_BASE_URL;
const response = await fetch(`${API}/auth/me`, {
  credentials: "include",
  headers: { "Content-Type": "application/json" }
});
if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
const user = await response.json();
```

For state-changing requests, copy the `csrf_token` cookie value into `X-CSRF-Token`:
```js
fetch(`${API}/applications`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
  body: JSON.stringify(application)
});
```

The frontend is integrated through `frontend/src/api/backendClient.js`; endpoint and auth details are documented in `backend/docs/FRONTEND_INTEGRATION.md`.

## Deployment and production checklist

1. Choose a Python host that currently supports your app and check its free-tier quotas/cold starts; plans change, and no host is assumed here.
2. Configure environment variables through the host's secret manager.
3. Use Atlas private/network-restricted access, backups, and least-privilege DB credentials.
4. Use private S3-compatible object storage with encryption, signed short-lived URLs, retention policies, and malware scanning.
5. Set `APP_ENV=production`, `COOKIE_SECURE=true`, a strong `JWT_SECRET_KEY`, exact `FRONTEND_ORIGINS`, and HTTPS.
6. Configure verified recovery via a real SMS/email provider before enabling password resets.
7. Review the service document checklist with the shop and local authorities; only publish verified checklists.
8. Run the full test suite and security checks, including IDOR tests, on a disposable staging database.
9. Verify backup restoration and monitor readiness, error rates, and storage usage.

## Backup / restore

Use MongoDB Atlas automated backups if included in your selected plan, or schedule `mongodump` to a secured location. Protect dumps as sensitive data, encrypt them, restrict access, and regularly test restoration. Never store backup credentials in the repository.

## Known limitations

The local API readiness endpoint currently reports MongoDB connected. This does not verify production deployment or live Cloudinary/S3 integration. Production CORS, secure cookies, and private storage require production configuration and integration tests. Password recovery remains disabled until a verified provider is configured. Malware scanning and business-approved checklists are not supplied. Do not process real identity documents until those prerequisites are complete and verified.

## Optional Base44 CLI Workflow

Use this repository to run and edit the app locally, then publish changes back through Base44.

Any change pushed to the repo will also be reflected in the Base44 Builder.

## Prerequisites

1. Clone the repository using the project's Git URL.
2. Navigate to the project directory.
3. Install dependencies: `npm install`.
4. Install the Base44 CLI: `npm install -g base44@latest`.
5. Install [Deno](https://docs.deno.com/runtime/getting_started/installation/) — the local Base44 backend runs on it.

Run `base44 --help` (or see the [CLI reference](https://docs.base44.com/developers/references/cli/commands/introduction)) for the full command surface.

## Run Locally

Three commands, from the project root:

```bash
base44 login   # one-time per machine
base44 link    # one-time per clone
base44 dev     # local backend + frontend together
```

Open the frontend URL that `base44 dev` prints (typically `http://localhost:5173`).

Notes:

- **Every fresh clone needs `base44 link`.** It writes `base44/.app.jsonc` (the app-id pointer), which is deliberately gitignored. Your app id is in the Builder URL (`app.base44.com/apps/<id>/...`); `base44 link --help` shows the non-interactive flags.
- **`base44 dev` runs the frontend for you** (via `site.serveCommand` in this repo's `base44/config.jsonc`) — never run `npm run dev` yourself: alone it serves a UI with no backend behind it (`[base44] Proxy not enabled`, every `/api` call fails), and alongside `base44 dev` the second Vite silently takes the next port and you end up looking at the wrong one.
- **The app must be published at least once for the UI to load under `base44 dev`.** The frontend boots by fetching app settings from the hosted app; before the first publish that fails and every page redirects to login. The local API works regardless.
- Entities, functions, and auth run locally — entity data is **in-memory only**, wiped when `base44 dev` restarts. Everything else (Core integrations, OAuth login) is forwarded to your deployed app. Full breakdown: [Local development overview](https://docs.base44.com/developers/backend/overview/local-dev/local-development-overview).

## Frontend Only, Hosted Backend

To work on just the frontend against your app's live hosted backend:

```bash
base44 dev --remote
```

⚠️ In this mode writes go to your app's **production data** — plain `base44 dev` keeps everything local.

## Publish Your Changes

After pushing your changes to git, open the Base44 dashboard and publish the app:

```bash
base44 dashboard open
```

This repo syncs to Base44 through git, so publish from the dashboard rather than `base44 deploy` — a CLI deploy ships your local tree directly, bypassing the sync, and the deployed state silently diverges from the repo.

## Docs & Support

GitHub integration: [https://docs.base44.com/developers/app-code/local-development/github](https://docs.base44.com/developers/app-code/local-development/github)

Local development: [https://docs.base44.com/developers/backend/overview/local-dev/local-development-overview](https://docs.base44.com/developers/backend/overview/local-dev/local-development-overview)

Support: [https://app.base44.com/support](https://app.base44.com/support)
