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

Services expose `document_requirements` for uploadable files and `form_requirements` for information the customer enters. Each new application snapshots both lists and the customer-facing service name, description, document category, and section reference at creation; later catalog edits do not rewrite those historical fields. Customers save the entered values in `application_data` when patching a draft; required values and required documents must be present before submission.

Service catalog fields are additive: `section_id` optionally references a managed service category while the legacy `category` string remains supported for filtering and older clients. Services may also set `customer_instructions`, `estimated_processing_time`, `pricing`, `display_order`, `is_featured`, and `thumbnail_alt_text`; customer-facing text accepts plain strings or localized maps where supported. These fields participate in service version snapshots. Application checklist/form snapshots and service name/category display details are captured at creation.

`GET /services/categories` lists visible categories ordered by `display_order`. Admins can include hidden categories with `?include_hidden=true`, create them with `POST /services/categories`, edit name/description/visibility/order/slug with `PATCH /services/categories/{category_id}`, and delete with `DELETE /services/categories/{category_id}`. In-use categories (including categories retained in service-version snapshots) cannot be deleted; hide them with `is_visible: false` instead. Category names and descriptions are localized maps; slugs are lowercase identifiers. `GET /services` additionally accepts `section_id`; its existing `category` filter remains unchanged. Public service listing/detail excludes services assigned to hidden sections; an assigned section must be visible before publishing.

Admins upload or replace thumbnails with multipart `PUT /services/{service_id}/thumbnail` using a `file` field. The upload is authenticated, uses the configured private `STORAGE_PROVIDER`, checks extension, declared MIME type, actual image content, and `MAX_UPLOAD_SIZE_MB`, and accepts JPEG/PNG only. Replacements increment the service version and retain prior references in service/version history; deleting a service with no applications removes its current and historical thumbnail objects when the provider is available. Archiving only unpublishes the service and keeps its thumbnail. `GET /services/{service_id}/thumbnail` serves published thumbnails to visitors and permits admins to preview drafts. Local/S3 content is streamed through the API; Cloudinary uses a five-minute authenticated signed URL redirect. API service representations expose only safe thumbnail metadata and the API thumbnail path; storage keys, credentials, and permanent provider URLs are never returned. No new environment variable is required: configure existing private storage settings and `MAX_UPLOAD_SIZE_MB` as described in deployment guidance. Local storage remains development-only.

Each document requirement may include `accepted_formats` (PDF/JPEG/PNG extension or MIME values) and `max_size_mb`. The upload-intent API enforces these per-item settings in addition to the global `MAX_UPLOAD_SIZE_MB`, and the customer form uses the same limits as hints. Checklist order is retained in the application snapshot.

For uploads, POST JSON to `/applications/{id}/documents/upload-url` with `filename`, `content_type`, `file_size`, and `checklist_item_id`. With S3-compatible storage the API returns a five-minute signed POST URL and fields; upload those fields, then POST `{"upload_id":"..."}` as JSON to `/applications/{id}/documents/confirm`. Local and Cloudinary storage return `upload_mode: multipart`; confirm with multipart fields `upload_id` and `file`. Cloudinary uploads pass through the backend so it can check file size, declared type, extension, actual content, and checklist membership before storing the bytes as an authenticated/private asset. MongoDB stores the generated Cloudinary `public_id`, provider, and metadata, not an expiring URL.

Both download routes authorize the requesting user against the application before accessing a file. `/documents/{id}/download-url` returns a five-minute signed URL for S3 or Cloudinary; local files use the authenticated `/documents/{id}/download` endpoint. The latter streams local/S3 content and redirects Cloudinary requests to a newly generated five-minute signed URL. Do not persist or reuse these signed URLs as file references. New uploads record their storage provider; records created before provider metadata existed continue using their original local or S3 keys. No existing files are migrated when the configured provider changes.

Once an application reaches `Completed by Shop`, an owner/admin with task-management permission can upload one final document with multipart `POST /applications/{application_id}/issued-document`; no separate completed checklist task is required. The API verifies the application status, customer account, role permission, file type, size, and actual file content, then binds the private file record to that application's customer. The owner/admin can share it with `POST /applications/{application_id}/issued-document/share`. Sharing records `shared_at`/`shared_by`, writes an audit event, and notifies the customer. Customers only see shared issued documents in the application document list and can download them through authenticated, application-scoped download endpoints. Storage keys and reusable public URLs are never returned. Startup index creation enforces at most one issued-document record per application.

`GET /documents/released` is customer-only and returns only `document_kind: issued` files whose `shared_at` is set and whose customer and application IDs both match the signed-in customer. Customer-submitted verification files are never included. View/download still uses the authorization-checked `/documents/{id}/download-url` route. `GET /notifications/unread-documents` returns unread release, document-review, replacement-request, and application-comment notifications for the customer; referenced documents are checked against the same customer/application binding. `POST /notifications/{id}/read?application_id=...` optionally validates the related application and persists `is_read` without deleting the document or notification. A release notification stores `related_document_id` so the UI can deep-link to that exact file.

Owners/admins can search released completed documents with `GET /applications/completed-documents?q=...&page=...&page_size=...`. MongoDB aggregation searches the filename, document ObjectId, application number, and customer name, returns shared issued files only, sorts by release date, and paginates server-side within the existing completed-work retention/role scope. The endpoint exposes file metadata only, never storage keys or permanent URLs.

Dashboard membership follows persisted state. `GET /applications` returns in-progress applications in workflow order (most advanced status first, then most recently updated); owner/admin/staff views omit centre-completed applications, while a customer's own list omits a completed application only after its matching issued document has a persisted `shared_at`. `GET /applications/awaiting-customer-sharing` returns centre-completed applications without a shared matching issued document, including cases where no final document has been uploaded or an uploaded document has not yet been shared. `GET /applications/completed-work` returns only centre-completed applications whose issued document is bound to that application's customer and has a persisted `shared_at`. Both final-document dashboard endpoints enforce owner/admin scope, staff assignment scope, or the requesting customer's own application scope and the existing 45-day application retention filter.

Owners/admins can upload or replace an issued document while it remains unshared. Replacements are recorded in the document's replacement history and are rejected if sharing has already occurred or the record changed concurrently. The workspace renders the upload/replace and share actions in **Awaiting Customer Sharing**; a successful share moves the application to **Completed Tasks** on the next refresh. Customers see shared applications in their own **Completed Tasks** section, not their active application list.

Completed tasks are returned for up to 45 days after `completed_at`; expired tasks are excluded from list and detail endpoints. A background cleanup worker starts with the API, runs immediately, then hourly. It deletes each expired completed-task record and deletes the related application, application-scoped history/comments/notifications/upload intents, and stored customer/final document files when the application is `Completed by Shop` and all remaining tasks are terminal and outside their retention windows. Applications in any other status are preserved for workflow or potential legal/operational review; their expired task records are removed without deleting the application data. Completed applications or tasks without reliable completion timestamps are preserved rather than assigned speculative dates. Global customer accounts and audit logs are retained for account continuity and operational accountability.

`GET /tasks` and `GET /tasks/{task_id}` include application, customer, and submitted-document summaries for authorized task readers. Owners/admins can read managed tasks; staff can read only their assigned tasks, and an assigned staff member receives application details only when the application itself is assigned to them. These summaries contain no storage references. `GET /applications` and `GET /applications/{application_id}` include customer contact details for authorized owner/staff/admin users only.

Customer profile photos can be uploaded or replaced with multipart `PUT /auth/me/photo` using a `file` field. The endpoint is customer-only, requires cookie CSRF protection, accepts JPEG or PNG, and stores the backend-generated storage reference and metadata in the user's MongoDB record. The response and `/auth/me` expose photo metadata but never the storage key or signed URL.

Sensitive changes use JSON bodies: staff creation, admin role/status/permission updates, physical document receipt, document review, and replacement requests. Customer application responses omit internal notes, assignment, priority, and internal due dates. Customer comment reads omit internal comments.

Login is limited to five attempts per minute per client IP and normalized phone using MongoDB counters shared across app workers.
