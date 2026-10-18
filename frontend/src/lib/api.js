export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Thin wrapper around fetch for the backend JSON API. Returns {ok, status, data}.
export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => null)
  return { ok: res.ok, status: res.status, data }
}
