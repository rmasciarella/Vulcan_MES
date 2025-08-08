import { createServerClient } from '@/infrastructure/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const redirectTo = requestUrl.searchParams.get('redirectTo') || '/dashboard'
  const error = requestUrl.searchParams.get('error')
  const errorDescription = requestUrl.searchParams.get('error_description')

  // Handle OAuth errors
  if (error) {
    console.error('OAuth error:', error, errorDescription)
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(error)}&error_description=${encodeURIComponent(errorDescription || '')}`, requestUrl.origin)
    )
  }

  // Handle missing authorization code
  if (!code) {
    console.error('Missing authorization code in callback')
    return NextResponse.redirect(
      new URL('/login?error=missing_code', requestUrl.origin)
    )
  }

  try {
    const supabase = await createServerClient()

    // Exchange code for session
    const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

    if (exchangeError) {
      console.error('Error exchanging code for session:', exchangeError)
      return NextResponse.redirect(
        new URL(`/login?error=auth_callback_error&error_description=${encodeURIComponent(exchangeError.message)}`, requestUrl.origin)
      )
    }

    // Verify we have a valid session
    if (!data.session || !data.user) {
      console.error('No session or user after code exchange')
      return NextResponse.redirect(
        new URL('/login?error=session_error', requestUrl.origin)
      )
    }

    // Success - redirect to intended page
    const response = NextResponse.redirect(new URL(redirectTo, requestUrl.origin))
    
    // Set session in cookies for SSR
    response.cookies.set({
      name: 'supabase-auth-token',
      value: data.session.access_token,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: data.session.expires_in,
    })

    return response

  } catch (error) {
    console.error('Unexpected error in auth callback:', error)
    return NextResponse.redirect(
      new URL('/login?error=unexpected_error', requestUrl.origin)
    )
  }
}