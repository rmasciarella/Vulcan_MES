#!/usr/bin/env node
/*
  Central environment validator
  - Supports .env files locally (basic parser) and CI-provided env
  - Validates variables for contexts: build | test | deploy
  - Mirrors key rules from apps/frontend/src/shared/lib/env.ts (no external deps)
*/

const fs = require('fs')
const path = require('path')

function loadDotEnvIfPresent() {
  const candidates = [
    path.resolve(process.cwd(), '.env'),
    path.resolve(process.cwd(), '.env.local'),
  ]
  for (const file of candidates) {
    if (fs.existsSync(file)) {
      const content = fs.readFileSync(file, 'utf8')
      parseAndApplyEnv(content)
    }
  }
}

function parseAndApplyEnv(src) {
  // Minimal .env parser (no variable interpolation)
  const lines = src.split(/\r?\n/)
  for (const raw of lines) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq === -1) continue
    const key = line.slice(0, eq).trim()
    let val = line.slice(eq + 1).trim()
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1)
    }
    if (!(key in process.env)) process.env[key] = val
  }
}

function fail(msg, hints = []) {
  console.error('\n❌ Environment validation failed:')
  console.error('   ' + msg)
  for (const h of hints) console.error('   → ' + h)
  process.exit(1)
}

function warn(msg) {
  console.warn('⚠️  ' + msg)
}

function isUrl(value) {
  try {
    new URL(value)
    return true
  } catch {
    return false
  }
}

function boolFromStr(v, def = false) {
  if (v === undefined) return def
  return String(v).toLowerCase() === 'true'
}

function getContext() {
  // --context flag overrides
  const idx = process.argv.indexOf('--context')
  if (idx !== -1 && process.argv[idx + 1]) return process.argv[idx + 1]
  // Infer from CI
  if (process.env.GITHUB_WORKFLOW || process.env.CI) return 'build'
  return 'build'
}

function validateFrontend(envName) {
  const errors = []
  const hints = []

  // Legacy mapping support (mirrors env.ts)
  if (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY && !process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
    warn('Using legacy NEXT_PUBLIC_SUPABASE_ANON_KEY; prefer NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  }

  // Required public vars
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !isUrl(process.env.NEXT_PUBLIC_SUPABASE_URL)) {
    errors.push('NEXT_PUBLIC_SUPABASE_URL is missing or not a valid URL')
    hints.push('Set NEXT_PUBLIC_SUPABASE_URL to your Supabase project URL (https://...supabase.co)')
  }
  if (!process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
    errors.push('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is required')
    hints.push('Expose a publishable key; safe to use in client')
  }

  // Production safeguards
  const isProd = envName === 'production' || process.env.NEXT_PUBLIC_APP_ENV === 'production' || process.env.NODE_ENV === 'production'
  const mock = boolFromStr(process.env.NEXT_PUBLIC_ENABLE_MOCK_DATA, false)
  const debugUi = boolFromStr(process.env.NEXT_PUBLIC_ENABLE_DEBUG_UI, false)
  if (isProd && mock) {
    errors.push('NEXT_PUBLIC_ENABLE_MOCK_DATA cannot be true in production')
    hints.push('Ensure NEXT_PUBLIC_ENABLE_MOCK_DATA=false for production builds')
  }
  if (isProd && debugUi) {
    errors.push('NEXT_PUBLIC_ENABLE_DEBUG_UI must be false in production')
    hints.push('Ensure NEXT_PUBLIC_ENABLE_DEBUG_UI=false for production builds')
  }

  return { errors, hints }
}

function validateServer(envName, context) {
  const errors = []
  const hints = []

  // Legacy mapping support
  if (process.env.SUPABASE_SERVICE_KEY && !process.env.SUPABASE_SECRET) {
    warn('Using legacy SUPABASE_SERVICE_KEY; prefer SUPABASE_SECRET')
    process.env.SUPABASE_SECRET = process.env.SUPABASE_SERVICE_KEY
  }

  // Require SUPABASE_SECRET for non-dev contexts and always in CI
  const requireSecret = context === 'deploy' || envName !== 'development' || !!process.env.CI
  if (requireSecret && !process.env.SUPABASE_SECRET) {
    errors.push('SUPABASE_SECRET is required for server operations')
    hints.push('Provide SUPABASE_SECRET via CI secrets or local .env')
  }

  return { errors, hints }
}

function validateBackend(envName) {
  // Backend is Python; validate presence of common envs when running backend tests or build-docker
  const errors = []
  const hints = []
  if (process.env.CI) {
    // Only soft-check here; backend jobs define their own defaults in CI
    if (!process.env.DATABASE_URL) {
      warn('DATABASE_URL not set; backend tests/jobs must provide it')
    }
  }
  return { errors, hints }
}

function main() {
  loadDotEnvIfPresent()

  const context = getContext() // build | test | deploy
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV || 'development').toLowerCase()

  const results = []
  results.push(validateFrontend(appEnv))
  results.push(validateServer(appEnv, context))
  results.push(validateBackend(appEnv))

  const errors = results.flatMap(r => r.errors)
  const hints = results.flatMap(r => r.hints)

  if (errors.length > 0) {
    fail(errors.join('\n - '), hints)
  }

  console.log('✅ Environment validation passed for context=%s, appEnv=%s', context, appEnv)
}

main()
