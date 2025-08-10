import { createServerClient } from '@/infrastructure/supabase'
import { SupabaseJobRepository } from '@/infrastructure/supabase/repositories/supabase-job-repository'

export const dynamic = 'force-dynamic'

export default async function JobsDebugPage() {
  const supabase = await createServerClient()
  const repo = new SupabaseJobRepository(supabase)
  let jobs: any[] = []
  let error: string | null = null

  try {
    jobs = await repo.listRecent(10)
  } catch (e: any) {
    error = e?.message ?? 'Unknown error'
  }

  return (
    <pre style={{ padding: 16, fontSize: 12 }}>
      {JSON.stringify({ ok: !error, count: jobs.length, sample: jobs[0] ?? null, error }, null, 2)}
    </pre>
  )
}
