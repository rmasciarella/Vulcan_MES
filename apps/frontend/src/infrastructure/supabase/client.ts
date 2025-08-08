import { createBrowserClient as createSupabaseBrowserClient } from '@supabase/ssr'
import { Database } from '@/types/supabase'
import { env } from '@/shared/lib/env'
import { createMockSupabaseClient } from './mock-client'

export function createBrowserClient() {
  if (env.NEXT_PUBLIC_ENABLE_MOCK_DATA) {
    return createMockSupabaseClient() as unknown as ReturnType<typeof createSupabaseBrowserClient<Database>>
  }
  return createSupabaseBrowserClient<Database>(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  )
}
