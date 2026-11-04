const LOCAL_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const SAME_ORIGIN_API_BASE_URL = '/api/v1';

function normalizeApiBaseUrl(baseUrl) {
  const configuredApiBaseUrl = baseUrl.replace(/\/+$/, '');
  if (/\/api\/v1$/i.test(configuredApiBaseUrl)) return configuredApiBaseUrl;
  if (/\/api$/i.test(configuredApiBaseUrl)) return `${configuredApiBaseUrl}/v1`;
  return `${configuredApiBaseUrl}/api/v1`;
}

export function resolveApiBaseUrl(configuredApiBaseUrl, isDevelopment) {
  if (!isDevelopment) return SAME_ORIGIN_API_BASE_URL;
  return normalizeApiBaseUrl(configuredApiBaseUrl || LOCAL_API_BASE_URL);
}
