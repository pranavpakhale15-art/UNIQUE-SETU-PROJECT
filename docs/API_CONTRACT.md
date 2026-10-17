# API contract and integration notes

Base URL: `http://127.0.0.1:8000/api/v1` in local development.

Authentication uses HttpOnly access and refresh cookies; tokens are not returned in JSON. Browser clients must use `credentials: "include"`. A readable `csrf_token` cookie is issued; every cookie-authenticated state-changing request must send its value in `X-CSRF-Token`. Production must use HTTPS and `COOKIE_SECURE=true`. Refresh tokens are opaque, stored only as hashes, and rotated on use.

Most errors use FastAPI's `{"detail":"..."}` shape. Validation errors use FastAPI's standard 422 response. Do not rely on frontend-supplied role/customer/staff identifiers for authorization.

Pagination response:
```json
{"items":[],"page":1,"page_size":20,"total":0,"pages":0}
```

Status values:
- Draft
- Submitted by Customer
- Received by Shop
- Documents Under Review
- Documents Incomplete
- Correction Requested
- Ready for Processing
- In Progress
- Submitted to Government Authority
- Awaiting Government Decision
- Approved by Authority
- Rejected by Authority
- Completed by Shop
- Rejected by Shop
- Cancelled

`Approved by Authority` means the relevant authority approved the application; `Completed by Shop` means the shop's workflow is complete. These are distinct. `Rejected by Shop` is an owner/admin decision made during the shop's review, separate from a government authority rejection.

Services expose `document_requirements` for uploadable files and `form_requirements` for information the customer enters. Applications snapshot both on creation. Customers save the entered values in `application_data` when patching a draft; required values and required documents must be present before submission.

For uploads, POST JSON to `/applications/{id}/documents/upload-url` with `filename`, `content_type`, `file_size`, and `checklist_item_id`. With S3-compatible storage the API returns a five-minute signed POST URL and fields; upload those fields, then POST `{"upload_id":"..."}` as JSON to `/applications/{id}/documents/confirm`. Local and Cloudinary storage return `upload_mode: multipart`; confirm with multipart fields `upload_id` and `file`. Cloudinary uploads pass through the backend so it can check file size, declared type, extension, actual content, and checklist membership before storing the bytes as an authenticated/private asset. MongoDB stores the generated Cloudinary `public_id`, provider, and metadata, not an expiring URL.

Both download routes authorize the requesting user against the application before accessing a file. `/documents/{id}/download-url` returns a five-minute signed URL for S3 or Cloudinary; local files use the authenticated `/documents/{id}/download` endpoint. The latter streams local/S3 content and redirects Cloudinary requests to a newly generated five-minute signed URL. Do not persist or reuse these signed URLs as file references. New uploads record their storage provider; records created before provider metadata existed continue using their original local or S3 keys. No existing files are migrated when the configured provider changes.

Once an application reaches `Completed by Shop`, an owner/admin with task-management permission can upload one final document with multipart `POST /applications/{application_id}/issued-document`; no separate completed checklist task is required. The API verifies the application status, customer account, role permission, file type, size, and actual file content, then binds the private file record to that application's customer. The owner/admin can share it with `POST /applications/{application_id}/issued-document/share`. Sharing records `shared_at`/`shared_by`, writes an audit event, and notifies the customer. Customers only see shared issued documents in the application document list and can download them through authenticated, application-scoped download endpoints. Storage keys and reusable public URLs are never returned. Startup index creation enforces at most one issued-document record per application.

Dashboard membership follows persisted state. `GET /applications` returns in-progress applications in workflow order (most advanced status first, then most recently updated); owner/admin/staff views omit centre-completed applications, while a customer's own list omits a completed application only after its matching issued document has a persisted `shared_at`. `GET /applications/awaiting-customer-sharing` returns centre-completed applications without a shared matching issued document, including cases where no final document has been uploaded or an uploaded document has not yet been shared. `GET /applications/completed-work` returns only centre-completed applications whose issued document is bound to that application's customer and has a persisted `shared_at`. Both final-document dashboard endpoints enforce owner/admin scope, staff assignment scope, or the requesting customer's own application scope and the existing 45-day application retention filter.

Owners/admins can upload or replace an issued document while it remains unshared. Replacements are recorded in the document's replacement history and are rejected if sharing has already occurred or the record changed concurrently. The workspace renders the upload/replace and share actions in **Awaiting Customer Sharing**; a successful share moves the application to **Completed Tasks** on the next refresh. Customers see shared applications in their own **Completed Tasks** section, not their active application list.

Completed tasks are returned for up to 45 days after `completed_at`; expired tasks are excluded from list and detail endpoints. A background cleanup worker starts with the API, runs immediately, then hourly. It deletes each expired completed-task record and deletes the related application, application-scoped history/comments/notifications/upload intents, and stored customer/final document files when the application is `Completed by Shop` and all remaining tasks are terminal and outside their retention windows. Applications in any other status are preserved for workflow or potential legal/operational review; their expired task records are removed without deleting the application data. Completed applications or tasks without reliable completion timestamps are preserved rather than assigned speculative dates. Global customer accounts and audit logs are retained for account continuity and operational accountability.

`GET /tasks` and `GET /tasks/{task_id}` include application, customer, and submitted-document summaries for authorized task readers. Owners/admins can read managed tasks; staff can read only their assigned tasks, and an assigned staff member receives application details only when the application itself is assigned to them. These summaries contain no storage references. `GET /applications` and `GET /applications/{application_id}` include customer contact details for authorized owner/staff/admin users only.

Customer profile photos can be uploaded or replaced with multipart `PUT /auth/me/photo` using a `file` field. The endpoint is customer-only, requires cookie CSRF protection, accepts JPEG or PNG, and stores the backend-generated storage reference and metadata in the user's MongoDB record. The response and `/auth/me` expose photo metadata but never the storage key or signed URL.

Sensitive changes use JSON bodies: staff creation, admin role/status/permission updates, physical document receipt, document review, and replacement requests. Customer application responses omit internal notes, assignment, priority, and internal due dates. Customer comment reads omit internal comments.

Login is limited to five attempts per minute per client IP and normalized phone using MongoDB counters shared across app workers.
