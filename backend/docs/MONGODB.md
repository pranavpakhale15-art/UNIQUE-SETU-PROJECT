# MongoDB data model

- `users`: identity, role, account status, password hash.
- `services`: localized catalog, versioned requirements, publication status.
- `service_categories`: localized dynamic service sections/categories, visibility and ordering; referenced categories are protected from deletion while current or versioned services use them.
- `applications`: customer/service reference, service version and checklist snapshot, state.
- `application_documents`: metadata and private storage key only; owner-issued files are customer-visible only after `shared_at` is set and customer/application IDs match. Customer-uploaded verification files remain separate. File bytes are stored outside MongoDB.
- `application_status_history`: append-only state changes.
- `application_tasks`: assigned staff tasks and due dates.
- `notifications`: recipient-scoped in-app notifications with persistent `is_read`, optional `related_document_id`, and deduplication key.
- `audit_logs`: sensitive administrative/business events.
- `sessions`: hashed refresh-token identifiers, user, expiry, user-agent, revocation state, and rotation references.
- `rate_limits`: fixed-window login counters keyed by hashed IP/phone identifiers; TTL cleanup.
- `document_upload_intents`: short-lived user/application-bound upload requests; TTL cleanup.
- `service_versions`: snapshots saved before successful service updates.
- Service thumbnail references and replacement history are stored with service records/version snapshots; image bytes remain in configured private storage.
- `application_comments`: customer-visible and internal comments.

See `app/database/indexes.py` for indexes. Supporting indexes cover customer/issued/shared document lookup, recipient/unread/document-notification lookup, and completed application searches. Notification deduplication uses a partial unique index only for string keys; startup replaces the prior sparse unique index when present. ObjectId references are used; MongoDB transactions are not assumed. Application status updates use compare-and-set on the prior status, while audit/history are separate writes and should be reconciled if a process fails between writes.

The application pings MongoDB on startup and closes the client during shutdown. Readiness returns HTTP 503 if the database ping fails. Production should use a least-privilege Atlas user with restricted network access and backups enabled.
