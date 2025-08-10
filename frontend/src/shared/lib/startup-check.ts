/* Dev-only startup check: logs missing env variables without crashing */
import { env } from './env'

function logMissing(name: string) {
  // eslint-disable-next-line no-console
  console.warn(`[env] Missing: ${name}. Some features may be disabled in development.`)
}

export function runStartupEnvCheck() {
  if (process.env.NODE_ENV === 'production') return

  let missing = 0
  if (!env.NEXT_PUBLIC_SUPABASE_URL) {
    logMissing('NEXT_PUBLIC_SUPABASE_URL')
    missing++
  }
  if (!(env as any).NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
    logMissing('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')
    missing++
  }
  if (typeof (env as any).SUPABASE_SECRET !== 'string' || !(env as any).SUPABASE_SECRET) {
    logMissing('SUPABASE_SECRET')
    missing++
  }

  if (missing === 0) {
    // eslint-disable-next-line no-console
    console.info('[env] All critical environment variables present for development.')
  } else {
    // eslint-disable-next-line no-console
    console.info(`[env] ${missing} missing env variable(s) detected. Using fallbacks where possible.`)
  }
}
