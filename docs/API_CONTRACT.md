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

Customer profile photos can be uploaded or replaced with multipart `PUT /auth/me/photo` using a `file` field. The endpoint is customer-only, requires cookie CSRF protection, accepts JPEG or PNG, and stores the backend-generated storage reference and metadata in the user's MongoDB record. The response and `/auth/me` expose photo metadata but never the storage key or signed URL.

Sensitive changes use JSON bodies: staff creation, admin role/status/permission updates, physical document receipt, document review, and replacement requests. Customer application responses omit internal notes, assignment, priority, and internal due dates. Customer comment reads omit internal comments.

Login is limited to five attempts per minute per client IP and normalized phone using MongoDB counters shared across app workers.
