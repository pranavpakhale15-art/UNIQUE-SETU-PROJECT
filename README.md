# Unique Solutions and Setu Kendra — Backend

Independent FastAPI + MongoDB backend intended to connect to an existing React frontend.

## Important implementation notes

- MongoDB is the only application database. No SQL database is used.
- Service seed data includes the 21 service names and Marathi document requirements supplied for them. Run `python -m scripts.seed_services` to publish the catalog; populated service checklists are preserved.
- Authentication uses Argon2id, short-lived session-bound access JWTs, and opaque refresh tokens stored only as hashes. Refresh rotates and revokes the prior session; logout, account suspension, role changes, and admin revocation invalidate sessions. Cookies are HttpOnly, SameSite-configurable, and state-changing cookie requests require `X-CSRF-Token` matching the readable `csrf_token` cookie. Login throttling is MongoDB-backed per IP and phone number.
- Forgot/reset password endpoints deliberately do not issue a reset token because no verified SMS/email recovery provider is configured.
- Local private file storage is provided for development. Production can use an S3-compatible private bucket or Cloudinary authenticated assets; signed download URLs expire after five minutes. File content is checked with `python-magic`; malware scanning is not implemented.
- The readiness endpoint returns HTTP 503 if MongoDB cannot be pinged. Startup also fails if MongoDB is not configured or reachable.
- Customers can browse published services and track applications. Owners/admins can review and progress applications; staff can access assigned application data and documents without verification or rejection permissions.
- No live MongoDB or object-storage integration was available during local verification.
- No production deployment has been performed or verified by this source package.

## Requirements

- Python 3.11, 3.12, or 3.13
- MongoDB Atlas or a local MongoDB instance
- A strong secret for `JWT_SECRET_KEY`

## Local setup (Windows PowerShell)

```powershell
cd unique-solutions-backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Edit `.env` and set `MONGODB_URI`, `MONGODB_DATABASE`, and a newly generated `JWT_SECRET_KEY` of at least 32 characters. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. The example uses a local MongoDB URI. Start local MongoDB with Docker if available:

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

In a second PowerShell window, start the frontend using the same `127.0.0.1` host configured for backend CORS:

```powershell
cd ..\unique-solutions-frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The frontend's `.env.example` points to `http://127.0.0.1:8000/api/v1`; copy it to `.env` if needed. Run `python -m scripts.seed_services` to publish the 21 provided Marathi service checklists. Sign in with a mobile number and password, selecting the account type assigned to that account; the backend verifies the selected type. Public registration is mobile-number based and creates customer accounts only.

Customer accounts can browse services, create applications, upload documents, and track status. Owners can review applications and documents, set priority and due dates, assign staff, and maintain follow-up tasks. Staff can only read assigned applications and download or copy application data. Admins manage accounts and service publication.

## Bootstrap privileged users

Run from the project root with `.env` configured:

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
- `POST /services` (admin)
- `PATCH /services/{service_id}` (admin)
- `POST /services/{service_id}/publish` (admin)
- `POST /services/{service_id}/archive` (admin)

### Applications
- `POST /applications`
- `GET /applications`
- `GET /applications/{application_id}`
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

The existing frontend's API calls must be inspected before claiming drop-in compatibility. This package has not inspected your React source code.

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

This backend has not been connected to this workspace's MongoDB because no local service, Docker daemon, or Atlas URI was available. S3-compatible storage, production CORS, secure cookies, and readiness are implemented but require real infrastructure configuration and integration tests. Password recovery remains disabled until a verified provider is configured. Malware scanning and business-approved checklists are not supplied. Do not process real identity documents until those prerequisites are complete and verified.
