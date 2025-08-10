import { createServerClient as createSupabaseServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { Database } from '@/types/supabase'
import { env } from '@/shared/lib/env'
import { createMockSupabaseClient } from './mock-client'

export async function createServerClient() {
  if (env.NEXT_PUBLIC_ENABLE_MOCK_DATA) {
    return createMockSupabaseClient() as unknown as ReturnType<typeof createSupabaseServerClient<Database>>
  }

  const cookieStore = await cookies()

  return createSupabaseServerClient<Database>(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options)
            })
          } catch {
            // The `set` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing
            // user sessions.
          }
        },
      },
    },
  )
}
