const configuredApiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/+$/, '');
const API_BASE_URL = /\/api\/v1$/i.test(configuredApiBaseUrl)
  ? configuredApiBaseUrl
  : /\/api$/i.test(configuredApiBaseUrl)
    ? `${configuredApiBaseUrl}/v1`
    : `${configuredApiBaseUrl}/api/v1`;
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export class APIError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.payload = payload;
  }
}

function readCookie(name) {
  if (typeof document === 'undefined') return '';
  const prefix = `${name}=`;
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
}

function buildHeaders(options) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const method = (options.method || 'GET').toUpperCase();
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie('csrf_token');
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  }
  return headers;
}

async function fetchResponse(path, options) {
  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method: (options.method || 'GET').toUpperCase(),
    headers: buildHeaders(options),
    credentials: 'include',
  });
}

async function refreshSession() {
  const response = await fetchResponse('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  return response.ok;
}

function formatValidationDetail(detail) {
  if (!Array.isArray(detail)) return '';

  return detail
    .map((issue) => {
      if (!issue || typeof issue !== 'object' || typeof issue.msg !== 'string') return '';

      const location = Array.isArray(issue.loc) ? issue.loc[issue.loc.length - 1] : null;
      const fieldNames = {
        full_name: 'Full name',
        mobile_number: 'Mobile number',
        password: 'Password',
        email: 'Email',
        preferred_language: 'Preferred language',
      };
      const field = typeof location === 'string' ? fieldNames[location] || location.replace(/_/g, ' ') : '';
      const message = issue.type === 'string_too_short' && Number.isInteger(issue.ctx?.min_length)
        ? `must be at least ${issue.ctx.min_length} characters`
        : issue.msg.replace(/^Value error,\s*/i, '');

      return field ? `${field}: ${message}` : message;
    })
    .filter(Boolean)
    .join('. ');
}

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || '';
  let payload = null;

  if (response.status !== 204) {
    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => null);
    } else {
      payload = await response.text().catch(() => null);
    }
  }

  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? payload.detail : payload;
    const validationMessage = formatValidationDetail(detail);
    const message = typeof detail === 'string'
      ? detail
      : validationMessage || (detail && typeof detail.message === 'string'
        ? detail.message
        : `Request failed with status ${response.status}`);
    throw new APIError(message, response.status, payload);
  }

  return payload;
}

export async function apiFetch(path, options = {}) {
  let response = await fetchResponse(path, options);
  const isAuthEndpoint = /^\/auth\/(login|register|refresh)(\/|$)/.test(path);

  if (response.status === 401 && !isAuthEndpoint) {
    if (await refreshSession()) response = await fetchResponse(path, options);
  }

  return parseResponse(response);
}

function localizedFields(record, field) {
  const values = record?.[field] && typeof record[field] === 'object' ? record[field] : {};
  return {
    [`${field}_mr`]: values.mr || record?.[`${field}_mr`] || '',
    [`${field}_en`]: values.en || record?.[`${field}_en`] || '',
    [`${field}_hi`]: values.hi || record?.[`${field}_hi`] || '',
  };
}

export function normalizeService(service) {
  const requirements = service.document_requirements || service.checklist || [];
  const normalizeRequirements = (items = [], prefix = 'item') => items.map((item, index) => {
    if (typeof item === 'string') {
      return { id: item, label_mr: item, label_en: item, label_hi: item, required: true };
    }
    const label = item.label || item.name || {};
    return {
      ...item,
      id: item.id || item.item_id || item._id || `${prefix}-${index + 1}`,
      ...localizedFields({ ...item, label }, 'label'),
    };
  });
  const checklist = normalizeRequirements(requirements, 'document');
  const formRequirements = normalizeRequirements(service.form_requirements || [], 'field');

  return {
    ...service,
    id: service.id || service._id,
    service_slug: service.service_slug || String(service.service_code || service._id || '').toLowerCase().replace(/_/g, '-'),
    checklist,
    form_requirements: formRequirements,
    ...localizedFields(service, 'name'),
    ...localizedFields(service, 'description'),
  };
}

export function normalizeApplication(application) {
  const service = application.service ? normalizeService(application.service) : null;
  return {
    ...application,
    id: application.id || application._id,
    application_id: application.application_id || application.application_number,
    customer_comments: application.customer_comments || application.customer_notes,
    service_name_mr: application.service_name_mr || service?.name_mr,
    service_name_en: application.service_name_en || service?.name_en,
    service_name_hi: application.service_name_hi || service?.name_hi,
    checklist_snapshot: (application.checklist_snapshot || []).map((item, index) => ({
      ...item,
      id: item.id || item.item_id || item._id || `item-${index + 1}`,
      ...localizedFields({ ...item, label: item.label || item.name || {} }, 'label'),
    })),
    form_requirements_snapshot: (application.form_requirements_snapshot || []).map((item, index) => ({
      ...item,
      id: item.id || item.item_id || item._id || `field-${index + 1}`,
      ...localizedFields({ ...item, label: item.label || item.name || {} }, 'label'),
    })),
  };
}

export function normalizeDocument(document) {
  const status = document.verification_status;
  return {
    ...document,
    id: document.id || document._id,
    document_kind: document.document_kind || 'customer_submission',
    review_status: status === 'correction_requested' ? 'replacement_requested' : status,
    submission_mode: document.submission_method === 'in_shop' ? 'physical' : 'online',
    upload_date: document.created_at,
    file_name: document.original_filename,
    reviewer_comments: document.reviewer_comment,
  };
}

export function normalizeMobileNumber(value) {
  const digits = value.replace(/\D/g, '');
  return digits.length === 12 && digits.startsWith('91') ? digits.slice(2) : digits;
}

export async function loginWithMobilePassword(mobile_number, password, account_type) {
  return apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ mobile_number, password, account_type }),
  });
}

export async function registerWithMobilePassword({ full_name, mobile_number, password, preferred_language = 'mr' }) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ full_name, mobile_number, password, preferred_language }),
  });
}

export async function logoutUser() {
  return apiFetch('/auth/logout', { method: 'POST' });
}

export async function getCurrentUser() {
  return apiFetch('/auth/me');
}

export async function requestPasswordReset(mobile_number) {
  return apiFetch('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ mobile_number }),
  });
}

export async function listServices(language = 'mr', includeUnpublished = false) {
  const unpublishedParam = includeUnpublished ? '&include_unpublished=true' : '';
  const result = await apiFetch(`/services?language=${encodeURIComponent(language)}&page=1&page_size=100${unpublishedParam}`);
  return { ...result, items: (result.items || []).map(normalizeService) };
}

export async function getService(serviceSlug) {
  return normalizeService(await apiFetch(`/services/${encodeURIComponent(serviceSlug)}`));
}

export async function listApplications() {
  const result = await apiFetch('/applications?page=1&page_size=100');
  return { ...result, items: (result.items || []).map(normalizeApplication) };
}

export async function listCompletedWork() {
  return apiFetch('/applications/completed-work');
}

export async function listAwaitingCustomerSharing() {
  return apiFetch('/applications/awaiting-customer-sharing');
}

export async function listNotifications() {
  return apiFetch('/notifications?page=1&page_size=100');
}

export async function updateApplicationStatus(applicationId, status, reason) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/status`, {
    method: 'POST',
    body: JSON.stringify({ status, reason: reason || null }),
  });
}

export async function updateApplicationOwnerFields(applicationId, fields) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/owner-fields`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });
}

export async function assignApplicationToStaff(applicationId, staffId) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/assign`, {
    method: 'POST',
    body: JSON.stringify({ staff_id: staffId }),
  });
}

export async function reviewApplicationDocument(documentId, verificationStatus, reviewerComment) {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/review`, {
    method: 'POST',
    body: JSON.stringify({ verification_status: verificationStatus, reviewer_comment: reviewerComment || null }),
  });
}

export async function listOwnerUsers(role) {
  const params = new URLSearchParams({ page: '1', page_size: '100' });
  if (role) params.set('role', role);
  return apiFetch(`/owner/users?${params}`);
}

export async function updateAdminUserRole(userId, role) {
  return apiFetch(`/admin/users/${encodeURIComponent(userId)}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });
}

export async function updateAdminUserStatus(userId, accountStatus) {
  return apiFetch(`/admin/users/${encodeURIComponent(userId)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ account_status: accountStatus }),
  });
}

export async function createStaffAccount(fullName, mobileNumber, password) {
  return apiFetch('/owner/staff', {
    method: 'POST',
    body: JSON.stringify({ full_name: fullName, mobile_number: mobileNumber, password }),
  });
}

export async function createService(service) {
  return apiFetch('/services', { method: 'POST', body: JSON.stringify(service) });
}

export async function updateService(serviceId, fields) {
  return apiFetch(`/services/${encodeURIComponent(serviceId)}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });
}

export async function publishService(serviceId) {
  return apiFetch(`/services/${encodeURIComponent(serviceId)}/publish`, { method: 'POST' });
}

export async function deleteService(serviceId) {
  return apiFetch(`/services/${encodeURIComponent(serviceId)}`, { method: 'DELETE' });
}

export async function archiveService(serviceId) {
  return apiFetch(`/services/${encodeURIComponent(serviceId)}/archive`, { method: 'POST' });
}

export async function createApplicationTask(task) {
  return apiFetch('/tasks', { method: 'POST', body: JSON.stringify(task) });
}

export async function listApplicationTasks() {
  return apiFetch('/tasks?page=1&page_size=100');
}

export async function getApplicationTask(taskId) {
  return apiFetch(`/tasks/${encodeURIComponent(taskId)}`);
}

export async function completeApplicationTask(taskId, completionNotes) {
  return apiFetch(`/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: 'POST',
    body: JSON.stringify({ completion_notes: completionNotes || null }),
  });
}

export async function uploadIssuedApplicationDocument(applicationId, file) {
  const form = new FormData();
  form.append('file', file);
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/issued-document`, {
    method: 'POST',
    body: form,
  });
}

export async function shareIssuedApplicationDocument(applicationId) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/issued-document/share`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function createApplication(serviceId, customerNotes) {
  const result = await apiFetch('/applications', {
    method: 'POST',
    body: JSON.stringify({ service_id: serviceId, customer_notes: customerNotes || null }),
  });
  return normalizeApplication(result);
}

export async function updateApplicationDraft(applicationId, customerNotes, applicationData) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ customer_notes: customerNotes || null, application_data: applicationData || {} }),
  });
}

export async function submitApplication(applicationId) {
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/submit`, { method: 'POST' });
}

export async function getApplication(applicationId) {
  const [application, history, documents, comments] = await Promise.all([
    apiFetch(`/applications/${encodeURIComponent(applicationId)}`),
    apiFetch(`/applications/${encodeURIComponent(applicationId)}/history`),
    apiFetch(`/applications/${encodeURIComponent(applicationId)}/documents`),
    apiFetch(`/applications/${encodeURIComponent(applicationId)}/comments`),
  ]);
  return {
    application: normalizeApplication(application),
    history: (history || []).map((item) => ({ ...item, id: item.id || item._id })),
    documents: (documents || []).map(normalizeDocument),
    comments: comments || [],
  };
}

export async function uploadApplicationDocument(applicationId, checklistItemId, file, replaceDocumentId) {
  const intent = await apiFetch(`/applications/${encodeURIComponent(applicationId)}/documents/upload-url`, {
    method: 'POST',
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      file_size: file.size,
      checklist_item_id: checklistItemId,
      replace_document_id: replaceDocumentId || null,
    }),
  });

  if (intent.upload_mode === 'signed_post') {
    const form = new FormData();
    Object.entries(intent.fields).forEach(([key, value]) => form.append(key, value));
    form.append('file', file);
    const uploadResponse = await fetch(intent.url, { method: 'POST', body: form });
    if (!uploadResponse.ok) throw new Error(`File storage rejected the upload (${uploadResponse.status})`);
    return apiFetch(`/applications/${encodeURIComponent(applicationId)}/documents/confirm`, {
      method: 'POST',
      body: JSON.stringify({ upload_id: intent.upload_id }),
    });
  }

  const form = new FormData();
  form.append('upload_id', intent.upload_id);
  form.append('file', file);
  return apiFetch(`/applications/${encodeURIComponent(applicationId)}/documents/confirm`, {
    method: 'POST',
    body: form,
  });
}

export async function downloadApplicationDocument(documentId, filename) {
  const downloadWindow = window.open('about:blank', '_blank');
  if (downloadWindow) downloadWindow.opener = null;
  let redirectedDownloadWindow = false;

  try {
    const info = await apiFetch(`/documents/${encodeURIComponent(documentId)}/download-url`);
    if (info.url) {
      if (downloadWindow) {
        downloadWindow.location.replace(info.url);
        redirectedDownloadWindow = true;
      } else {
        window.location.assign(info.url);
      }
      return;
    }

    const endpoint = info.download_endpoint || '';
    const prefix = '/api/v1';
    const path = endpoint.startsWith(prefix) ? endpoint.slice(prefix.length) : endpoint;
    let response = await fetchResponse(path, {});
    if (response.status === 401 && await refreshSession()) {
      response = await fetchResponse(path, {});
    }
    if (!response.ok) await parseResponse(response);

    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename || 'document';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  } finally {
    if (downloadWindow && !redirectedDownloadWindow) {
      downloadWindow.close();
    }
  }
}
