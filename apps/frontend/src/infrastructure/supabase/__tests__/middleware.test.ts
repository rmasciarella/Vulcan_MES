import { describe, it, expect, beforeEach, vi } from 'vitest'
import { updateSession } from '../../supabase/middleware'
import type { NextRequest } from 'next/server'

// Mock @supabase/ssr createServerClient to control auth.getUser()
vi.mock('@supabase/ssr', () => {
  return {
    createServerClient: (_url: string, _key: string, _opts: any) => {
      return {
        auth: {
          getUser: async () => ({ data: { user: (globalThis as any).__TEST_USER__ ?? null } }),
        },
      }
    },
  }
})

function makeRequest(path: string, origin = 'https://example.com', cookieJar?: Map<string, string>) {
  const url = new URL(path, origin)
  const jar = cookieJar ?? new Map<string, string>()

  const req = {
    url: url.toString(),
    nextUrl: url,
    cookies: {
      getAll: () => Array.from(jar.entries()).map(([name, value]) => ({ name, value })),
      get: (name: string) => (jar.has(name) ? { name, value: jar.get(name)! } : undefined),
      set: (name: string, value: string) => {
        jar.set(name, value)
      },
      delete: (name: string) => {
        jar.delete(name)
      },
    },
    headers: new Headers(),
  } as unknown as NextRequest

  return req
}

describe('supabase middleware - secure-by-default', () => {
  beforeEach(() => {
    ;(globalThis as any).__TEST_USER__ = null
  })

  it('redirects unauthenticated access to protected routes to /login with redirect param', async () => {
    ;(globalThis as any).__TEST_USER__ = null
    const req = makeRequest('/planning?view=week')
    const res = await updateSession(req)

    expect(res.status).toBe(307)
    const loc = res.headers.get('location')
    expect(loc).toBe('https://example.com/login?redirect=%2Fplanning%3Fview%3Dweek')
  })

  it('redirects authenticated access to public routes to /dashboard', async () => {
    ;(globalThis as any).__TEST_USER__ = { id: 'user1', app_metadata: {}, user_metadata: {} }
    const req = makeRequest('/')
    const res = await updateSession(req)

    expect(res.status).toBe(307)
    const loc = res.headers.get('location')
    expect(loc).toBe('https://example.com/dashboard')
  })

  it('does not interfere with API routes (bypass verification)', async () => {
    ;(globalThis as any).__TEST_USER__ = null
    const req = makeRequest('/api/health')
    const res = await updateSession(req)

    // NextResponse.next() defaults to 200 OK
    expect(res.status).toBe(200)
  })

  it('preserves auth callback flow (authenticated on /auth/* should not redirect)', async () => {
    ;(globalThis as any).__TEST_USER__ = { id: 'user1', app_metadata: {}, user_metadata: {} }
    const req = makeRequest('/auth/callback?code=abc')
    const res = await updateSession(req)

    // Should allow through (matcher may exclude in real runtime, but functionally no redirect)
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  it('avoids redirect loops on /auth/* paths when authenticated', async () => {
    ;(globalThis as any).__TEST_USER__ = { id: 'user1', app_metadata: {}, user_metadata: {} }
    const req = makeRequest('/auth/logout')
    const res = await updateSession(req)

    // Ensure no redirect to /dashboard, pass-through
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  it('allows unauthenticated access on public routes', async () => {
    ;(globalThis as any).__TEST_USER__ = null
    for (const path of ['/', '/login', '/signup', '/auth', '/auth/callback']) {
      const req = makeRequest(path)
      const res = await updateSession(req)
      expect(res.status).toBe(200)
      expect(res.headers.get('location')).toBeNull()
    }
  })

  it('sets role hint header when user has role metadata (non-enforcing)', async () => {
    ;(globalThis as any).__TEST_USER__ = { id: 'u1', app_metadata: { role: 'admin' }, user_metadata: {} }
    const req = makeRequest('/planning')
    const res = await updateSession(req)

    // Authenticated + protected -> should allow (no redirect) because user exists
    // But our logic still returns 200 unless on public route; here it's protected and user is present -> pass-through
    expect(res.status).toBe(200)
    expect(res.headers.get('x-rbac-role')).toBe('admin')
  })
})

