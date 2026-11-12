import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiUrl, request, setCsrfToken } from './client'

describe('apiUrl', () => {
  it('joins the base url and the path', () => {
    expect(apiUrl('/auth/me')).toBe('http://localhost:8000/api/auth/me')
    expect(apiUrl('auth/me')).toBe('http://localhost:8000/api/auth/me')
  })
})

describe('request', () => {
  afterEach(() => {
    setCsrfToken(null)
    vi.unstubAllGlobals()
  })

  it('sends the csrf token on mutating requests', async () => {
    setCsrfToken('token-value')
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await request('/clients', { method: 'POST', body: { name: 'Acme' } })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-CSRF-Token']).toBe('token-value')
    expect(init.credentials).toBe('include')
  })

  it('does not send the csrf token on reads', async () => {
    setCsrfToken('token-value')
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await request('/clients')

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('turns the error envelope into an ApiError', async () => {
    const body = JSON.stringify({
      error: { code: 'validation_error', message: 'Request validation failed.', request_id: 'abc' },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 422 })))

    await expect(request('/clients', { method: 'POST', body: {} })).rejects.toBeInstanceOf(ApiError)
  })

  it('surfaces field level validation messages', async () => {
    const body = JSON.stringify({
      error: {
        code: 'validation_error',
        message: 'Request validation failed.',
        details: { fields: [{ field: 'email', message: 'value is not a valid email address' }] },
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 422 })))

    try {
      await request('/clients', { method: 'POST', body: {} })
      expect.unreachable('the request should have failed')
    } catch (error) {
      const apiError = error as ApiError
      expect(apiError.code).toBe('validation_error')
      expect(apiError.fields?.[0].field).toBe('email')
    }
  })

  it('returns nothing for an empty response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(api.delete('/clients/1')).resolves.toBeUndefined()
  })
})
