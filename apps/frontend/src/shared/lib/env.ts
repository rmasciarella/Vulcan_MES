import { z } from 'zod'

// NOTE: Be strict in production, lenient in development to avoid crashing Next.js dev server
const isProd = process.env.NODE_ENV === 'production'

// Server-side environment variables schema
const serverEnvSchema = z.object({
  // NODE_ENV is automatically managed by Next.js - DO NOT SET MANUALLY
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  // Support both new and legacy naming with proper transforms
  SUPABASE_SECRET: z.string().min(1, 'SUPABASE_SECRET is required'),
}).transform((data) => ({
  ...data,
  // Ensure consistent field naming in output
  SUPABASE_SERVICE_KEY: data.SUPABASE_SECRET,
}))

// Client-side environment variables schema
const clientEnvSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.string().url('Invalid Supabase URL'),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z
    .string()
    .min(1, 'Supabase publishable key is required'),
  NEXT_PUBLIC_APP_NAME: z.string().default('Vulcan MES'),
  NEXT_PUBLIC_APP_ENV: z.enum(['development', 'staging', 'production']).default('development'),
  NEXT_PUBLIC_ENABLE_DEBUG_UI: z
    .string()
    .default('false')
    .transform((val) => val === 'true'),
  NEXT_PUBLIC_ENABLE_MOCK_DATA: z
    .string()
    .default('false')
    .transform((val) => {
      const enabled = val === 'true'
      // Production safeguard: never allow mock data in production
      if (isProd && enabled) {
        throw new Error('NEXT_PUBLIC_ENABLE_MOCK_DATA cannot be true in production')
      }
      return enabled
    }),
  // Health check configuration
  NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK: z
    .string()
    .default('false')
    .transform((val) => val === 'true'),
  NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS: z
    .string()
    .default('300000') // 5 minutes default
    .transform((val) => parseInt(val, 10)),
  NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS: z
    .string()
    .default('3600000') // 1 hour max
    .transform((val) => parseInt(val, 10)),
})

// Type definitions
type ServerEnv = z.infer<typeof serverEnvSchema>
type ClientEnv = z.infer<typeof clientEnvSchema>

function warnOnce(msg: string) {
  if (!(globalThis as any).__ENV_WARNED__) (globalThis as any).__ENV_WARNED__ = new Set<string>()
  const set: Set<string> = (globalThis as any).__ENV_WARNED__
  if (!set.has(msg)) {
    set.add(msg)
    // eslint-disable-next-line no-console
    console.warn(msg)
  }
}

// Validate server environment variables
function validateServerEnv(): ServerEnv {
  const result = serverEnvSchema.safeParse(process.env)
  if (result.success) return result.data

  // Legacy fallback: map SUPABASE_SERVICE_KEY -> SUPABASE_SECRET
  if (process.env.SUPABASE_SERVICE_KEY && !process.env.SUPABASE_SECRET) {
    warnOnce('Using legacy SUPABASE_SERVICE_KEY; please migrate to SUPABASE_SECRET')
    process.env.SUPABASE_SECRET = process.env.SUPABASE_SERVICE_KEY
    const retry = serverEnvSchema.safeParse(process.env)
    if (retry.success) return retry.data
  }

  // In production, fail fast
  if (isProd) {
    // eslint-disable-next-line no-console
    console.error('❌ Invalid server environment variables:', result.error.flatten().fieldErrors)
    throw new Error('Invalid server environment variables')
  }

  // In dev/test, warn and provide best-effort values to keep dev server running
  warnOnce('⚠️ Using fallback server env in non-production. Set SUPABASE_SECRET or SUPABASE_SERVICE_KEY to enable full functionality.')
  // Create fallback object that matches schema transform output
  const fallbackEnv = {
    NODE_ENV: (process.env.NODE_ENV as 'development' | 'test' | 'production') || 'development',
    SUPABASE_SECRET: process.env.SUPABASE_SERVICE_KEY || '',
  }
  // Apply same transform as schema to ensure type consistency
  return {
    ...fallbackEnv,
    SUPABASE_SERVICE_KEY: fallbackEnv.SUPABASE_SECRET,
  }
}

// Validate client environment variables
function validateClientEnv(): ClientEnv {
  // Legacy fallback: map NEXT_PUBLIC_SUPABASE_ANON_KEY -> NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  if (
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY &&
    !process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ) {
    warnOnce('Using legacy NEXT_PUBLIC_SUPABASE_ANON_KEY; please migrate to NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  }

  const input = {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV,
    NEXT_PUBLIC_ENABLE_DEBUG_UI: process.env.NEXT_PUBLIC_ENABLE_DEBUG_UI,
    NEXT_PUBLIC_ENABLE_MOCK_DATA: process.env.NEXT_PUBLIC_ENABLE_MOCK_DATA,
    NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK: process.env.NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK,
    NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS: process.env.NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS,
    NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS: process.env.NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS,
  }
  const result = clientEnvSchema.safeParse(input)
  if (result.success) return result.data

  if (isProd) {
    // eslint-disable-next-line no-console
    console.error('❌ Invalid client environment variables:', result.error.flatten().fieldErrors)
    throw new Error('Invalid client environment variables')
  }

  // In dev/test, warn and fill sensible fallbacks
  warnOnce('⚠️ Using fallback client env in non-production. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to enable Supabase features.')
  const enableDebug = (process.env['NEXT_PUBLIC_ENABLE_DEBUG_UI'] ?? 'false') === 'true'
  // Production safeguard: never enable mock data in production
  const enableMock = !isProd && (process.env['NEXT_PUBLIC_ENABLE_MOCK_DATA'] ?? 'false') === 'true'
  const enableHealthCheck = (process.env['NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK'] ?? 'false') === 'true'
  return {
    NEXT_PUBLIC_SUPABASE_URL: process.env['NEXT_PUBLIC_SUPABASE_URL'] || 'http://localhost:54321',
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env['NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'] || '',
    NEXT_PUBLIC_APP_NAME: process.env['NEXT_PUBLIC_APP_NAME'] || 'Vulcan MES',
    NEXT_PUBLIC_APP_ENV: ['development', 'staging', 'production'].includes(process.env['NEXT_PUBLIC_APP_ENV'] || '') 
      ? (process.env['NEXT_PUBLIC_APP_ENV'] as 'development' | 'staging' | 'production')
      : 'development',
    NEXT_PUBLIC_ENABLE_DEBUG_UI: enableDebug,
    NEXT_PUBLIC_ENABLE_MOCK_DATA: enableMock,
    NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK: enableHealthCheck,
    NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS: parseInt(process.env['NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS'] || '300000', 10),
    NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS: parseInt(process.env['NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS'] || '3600000', 10),
  }
}

// Export validated environment variables
export const serverEnv = typeof window === 'undefined' ? validateServerEnv() : ({} as ServerEnv)
export const clientEnv = validateClientEnv()

// Combined env object for convenience
export const env = {
  ...clientEnv,
  ...(typeof window === 'undefined' ? serverEnv : {}),
  // Legacy aliases - these are now properly typed thanks to schema transforms
  get NEXT_PUBLIC_SUPABASE_ANON_KEY() {
    warnOnce('NEXT_PUBLIC_SUPABASE_ANON_KEY is deprecated. Use NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY instead.')
    return clientEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  },
  // SUPABASE_SERVICE_KEY is now properly available from serverEnv transform
} as const
