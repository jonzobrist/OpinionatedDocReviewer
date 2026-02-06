export const DEFAULT_TENANT = 'local-dev';

export function getApiBase() {
  if (typeof window !== 'undefined') {
    const fromStorage = window.localStorage.getItem('odr_api_base');
    if (fromStorage) {
      return fromStorage;
    }
  }
  return process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8006/api';
}

export function setApiBase(value: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem('odr_api_base', value);
}

export function getTenantId() {
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem('odr_tenant_id') ?? DEFAULT_TENANT;
  }
  return DEFAULT_TENANT;
}

export function setTenantId(value: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem('odr_tenant_id', value);
}

export function buildHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-Tenant-Id': getTenantId()
  };
}

export async function apiFetch<T>(path: string, init?: RequestInit) {
  const base = getApiBase();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      ...buildHeaders(),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}
