# React Frontend Integration

The React customer flows use this API contract through `src/api/backendClient.js`. The API retains its MongoDB-oriented field names; the client normalizes service, application, and document responses for the existing UI.

## Base URL and cookies

Configure the React build with the backend origin, `/api` base, or full `/api/v1` base:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

The client adds `/api/v1` when it is omitted, or adds `/v1` when the value ends in `/api`.

All browser requests must use `credentials: "include"`. Registration and login set HttpOnly `access_token` and `refresh_token` cookies and a readable `csrf_token` cookie. Tokens are not returned in JSON. Send the `csrf_token` cookie value as `X-CSRF-Token` on every state-changing request, including logout and cookie-based refresh. Configure `FRONTEND_ORIGINS` to the exact frontend origin. Production requires HTTPS and `COOKIE_SECURE=true`.

```js
const API = import.meta.env.VITE_API_BASE_URL;

function readCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function apiFetch(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", readCookie("csrf_token"));
  }
  const response = await fetch(`${API}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}
```

## Authentication

- `POST /auth/register` with `full_name`, `mobile_number`, `password`, optional `email`, and `preferred_language`.
- `POST /auth/login` with `mobile_number`, `password`, and an optional `account_type` (`customer`, `staff`, `owner`, or `admin`). When supplied, the account type must match the account; it never grants or changes a role.
- Public registration always creates a customer account. Owner/admin accounts must be provisioned through the trusted bootstrap/admin workflow; staff accounts are created by an authorized owner/admin.
- `POST /auth/refresh` uses the refresh cookie and CSRF header; the response rotates both cookies.
- `POST /auth/logout` revokes the current session and clears cookies.
- `GET /auth/me` returns the signed-in public profile.
- `POST /auth/forgot-password` accepts `mobile_number` and returns a non-enumerating acknowledgement. Reset remains unavailable until a verified recovery provider is configured.

Passwords must be at least 10 characters and contain letters and numbers. Phone numbers are normalized to the last 10 digits of a valid Indian mobile number. Login is limited to five attempts per minute per IP and phone.

## Main endpoints

- Services: `GET /services`, `GET /services/{service_id}`. Search with `q`, filter by `category`, choose `language`, and paginate with `page`/`page_size`.
- Applications: `POST /applications`, `GET /applications`, `GET /applications/{application_id}`, `PATCH /applications/{application_id}`, `POST /applications/{application_id}/submit`, `POST /applications/{application_id}/status`, `GET /applications/{application_id}/history`, `GET|POST /applications/{application_id}/comments`.
- Documents: `POST /applications/{application_id}/documents/upload-url`, `POST /applications/{application_id}/documents/confirm`, `GET /applications/{application_id}/documents`, `POST /applications/{application_id}/issued-document`, `POST /applications/{application_id}/issued-document/share`, `GET /documents/{document_id}/download-url`, `POST /documents/{document_id}/review`, and `POST /documents/{document_id}/replacement-request`.
- Tasks: `GET|POST /tasks`, `GET|PATCH /tasks/{task_id}`, `POST /tasks/{task_id}/complete`.
- Notifications: `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{notification_id}/read`, `POST /notifications/read-all`.
- Readiness: `GET /health/ready`; a failed database ping returns 503.

All paths are relative to `/api/v1`. Authenticated users only see resources permitted by their role, permission set, and object ownership/assignment. Customer application responses exclude internal notes, priority, assignment, and internal due dates. Customers only see customer-visible comments.

Services can include both `document_requirements` (files to upload) and `form_requirements` (information to enter). New applications snapshot both lists. Save customer-provided values in `application_data` using the form requirement IDs when patching a draft. Required values and required documents are both checked before submission. Customers, owners, admins, and assigned staff can read the submitted application details; staff remain read-only.

Service-detail apply links send logged-out visitors to login with a validated same-origin `returnTo`; after login they return to that service. `POST /applications` remains customer-only and requires a valid authenticated session. Task list/detail responses include customer contact details and submitted document metadata only for authorized roles; staff must be assigned to both the task and the application to receive its application context. Owners/admins may upload a final document once the application is `Completed by Shop`, without a separate completed-task prerequisite, and may replace it until sharing. The dashboard's **Awaiting Customer Sharing** section includes centre-completed applications with no shared final document, including those without an upload; a successful share moves the matching application to **Completed Tasks** based on its persisted `shared_at`. The API orders active applications by workflow status and recent update time. Shared documents are listed in the customer's application account and trigger a `document.issued_available` notification linked to that application. Customers must sign in to view/download them; do not expose storage keys or cache signed URLs.

## Upload procedure

1. Request an upload intent with JSON, for example:

```json
{
  "filename": "identity.pdf",
  "content_type": "application/pdf",
  "file_size": 183420,
  "checklist_item_id": "identity-front"
}
```

2. In production, submit the returned `fields` and file to the returned signed S3-compatible `url` as `multipart/form-data`. The URL expires after five minutes. In local mode, POST `upload_id` and `file` as multipart fields to the returned `upload_endpoint`.
3. For S3 mode, confirm with JSON `{"upload_id":"..."}` at the confirm endpoint. The server validates the actual object content and size, verifies the user/application/checklist binding, and records it for review.
4. For downloads, call the authenticated download-URL endpoint. S3 mode returns a five-minute signed URL; local mode returns the authenticated API download endpoint.

Allowed files are PDF, JPEG, and PNG up to `MAX_UPLOAD_SIZE_MB`. The backend detects actual content with `python-magic`. Malware scanning is not implemented. Replacement requests must be authorized before a customer can replace a document.

## Status and errors

Application statuses are `Draft`, `Submitted by Customer`, `Received by Shop`, `Documents Under Review`, `Documents Incomplete`, `Correction Requested`, `Ready for Processing`, `In Progress`, `Submitted to Government Authority`, `Awaiting Government Decision`, `Approved by Authority`, `Rejected by Authority`, `Completed by Shop`, `Rejected by Shop`, and `Cancelled`. Government authority decisions and shop review outcomes are separate. Customers can cancel only early applications; owners/admins can manage shop review status.

Most errors use FastAPI's `{"detail": ...}` format. Important statuses include 401 unauthenticated, 403 forbidden/CSRF, 404 inaccessible or missing resource, 409 state conflict/missing required documents, 413 oversized upload, 422 invalid input, 429 login throttled, and 503 unavailable dependency.

List endpoints return `{ "items": [], "page": 1, "page_size": 20, "total": 0, "pages": 0 }`. Public services endpoints include published services; administrators can manage catalog entries. The seed includes the 21 supplied Marathi service checklists and publishes them when seeded.
