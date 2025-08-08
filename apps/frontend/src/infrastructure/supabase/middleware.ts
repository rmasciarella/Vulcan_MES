import { createServerClient as createSupabaseServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'
import { Database } from '@/types/supabase'
import { env } from '@/shared/lib/env'

/**
 * Public paths allowlist. Everything else is treated as protected by default.
 * Note: Do not include assets/static here; those are excluded via matcher.
 */
const PUBLIC_PATHS = ['/', '/login', '/signup', '/auth']

function isApiRoute(pathname: string) {
  return pathname.startsWith('/api')
}

function isPublicPath(pathname: string) {
  return PUBLIC_PATHS.some((p) => p === pathname || (p === '/auth' && pathname.startsWith('/auth')))
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createSupabaseServerClient<Database>(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  // 1) Refresh the auth token and fetch user
  const {
    data: { user },
  } = await supabase.auth.getUser()

  // Optional: set role hint header for downstream (prep for future RBAC; no enforcement here)
  const roleHint = (user?.app_metadata as any)?.role ?? (user?.user_metadata as any)?.role
  if (roleHint) {
    supabaseResponse.headers.set('x-rbac-role', String(roleHint))
  }

  const { pathname, search } = request.nextUrl

  // 2) Do not interfere with API routes
  if (isApiRoute(pathname)) {
    return supabaseResponse
  }

  // 3) Secure-by-default gating: all non-public routes require auth
  const unauthenticated = !user
  const onPublicRoute = isPublicPath(pathname)

  // If route is not public and user is unauthenticated -> redirect to /login with redirect param
  if (!onPublicRoute && unauthenticated) {
    const redirectTo = new URL('/login', request.url)
    const next = pathname + (search || '') // preserve intended destination
    redirectTo.searchParams.set('redirect', next)
    return NextResponse.redirect(redirectTo)
  }

  // If public route and authenticated -> redirect to dashboard (avoid auth flow loops)
  const isAuthFlow = pathname.startsWith('/auth')
  if (onPublicRoute && !unauthenticated && !isAuthFlow) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  // Otherwise, continue
  return supabaseResponse
}
