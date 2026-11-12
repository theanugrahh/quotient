const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api'

export class ApiError extends Error {
  status: number
  code: string
  fields?: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, fields?: { field: string; message: string }[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

let csrfToken: string | null = null

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export function resolveTarget(url: string): string {
  return /^https?:\/\//.test(url) ? url : apiUrl(url)
}

type RequestOptions = {
  method?: string
  body?: unknown
  formData?: FormData
  signal?: AbortSignal
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (method !== 'GET' && method !== 'HEAD' && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  const response = await fetch(apiUrl(path), {
    method,
    headers,
    credentials: 'include',
    signal: options.signal,
    body: options.formData ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
  })

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  const payload = (text ? safeParse(text) : null) as ErrorEnvelope | null

  if (!response.ok) {
    const error = payload?.error ?? {}
    throw new ApiError(
      response.status,
      error.code ?? 'request_failed',
      error.message ?? 'The request could not be completed.',
      error.details?.fields,
    )
  }

  return payload as T
}

type ErrorEnvelope = {
  error?: {
    code?: string
    message?: string
    details?: { fields?: { field: string; message: string }[] }
  }
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export const api = {
  get: <T,>(path: string, signal?: AbortSignal) => request<T>(path, { method: 'GET', signal }),
  post: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T,>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T,>(path: string, formData: FormData) => request<T>(path, { method: 'POST', formData }),
}
