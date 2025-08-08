import { NextResponse } from 'next/server'
import { createServerClient } from '@/infrastructure/supabase'

export async function GET() {
  try {
    const supabase = await createServerClient()

    // Check auth (won't throw if unauthenticated, just returns null)
    const { data: userResp, error: userErr } = await supabase.auth.getUser()
    if (userErr) {
      // Not fatal for health, but include for visibility
    }

    // Probe a lightweight table read; adjust table name if needed
    const { data, error } = await supabase
      .from('production_jobs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(1)

    const ok = !error

    return NextResponse.json({
      ok,
      authUser: userResp?.user ? { id: userResp.user.id } : null,
      dbProbe: {
        table: 'production_jobs',
        rows: data?.length ?? 0,
        error: error?.message ?? null,
      },
      timestamp: new Date().toISOString(),
    }, { status: ok ? 200 : 500 })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message ?? 'unknown' }, { status: 500 })
  }
}
