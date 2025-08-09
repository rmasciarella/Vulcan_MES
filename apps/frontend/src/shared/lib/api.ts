import { clientEnv } from './env'

export type ApiFetchOptions = RequestInit & { baseUrlOverride?: string }

function resolveUrl(path: string, baseUrl?: string): string {
  // Absolute URLs pass through
  if (/^https?:\/\//i.test(path)) return path
  if (baseUrl) return new URL(path, baseUrl).toString()
  // Fallback to relative path (same-origin) when no base provided
  return path
}

export async function apiFetch(input: string, init: ApiFetchOptions = {}): Promise<Response> {
  // Prefer explicit override, then env base URL; otherwise default to Netlify proxy '/api'
  const base = init.baseUrlOverride ?? clientEnv.NEXT_PUBLIC_API_URL ?? '/api'
  const url = resolveUrl(input, base)
  return fetch(url, init)
}

// Convenience helpers
export async function apiGet<T>(path: string, init: ApiFetchOptions = {}): Promise<T> {
  const res = await apiFetch(path, { ...init, method: 'GET' })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export async function apiPost<T>(path: string, body?: unknown, init: ApiFetchOptions = {}): Promise<T> {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export async function apiPatch<T>(path: string, body?: unknown, init: ApiFetchOptions = {}): Promise<T> {
  const res = await apiFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  })
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export async function apiDelete<T = void>(path: string, init: ApiFetchOptions = {}): Promise<T> {
  const res = await apiFetch(path, { method: 'DELETE', ...init })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
  try { return (await res.json()) as T } catch { return undefined as unknown as T }
}

export async function apiUpload<T>(path: string, formData: FormData, init: ApiFetchOptions = {}): Promise<T> {
  // Let the browser set multipart boundaries; do not set Content-Type
  const res = await apiFetch(path, { method: 'POST', body: formData, ...init })
  if (!res.ok) throw new Error(`UPLOAD ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

