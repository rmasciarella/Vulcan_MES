import { describe, it, expect, vi, beforeEach } from 'vitest'
import { JobUseCases } from '../job-use-cases'

function createMockSupabase() {
  const state: any[] = []

  const from = vi.fn().mockImplementation((table: string) => {
    const ctx: any = {
      _table: table,
      _filters: [],
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      eq: vi.fn().mockImplementation((col: string, val: any) => { ctx._filters.push({ type: 'eq', col, val }); return ctx }),
      in: vi.fn().mockImplementation((col: string, vals: any[]) => { ctx._filters.push({ type: 'in', col, vals }); return ctx }),
      ilike: vi.fn().mockImplementation((col: string, pattern: string) => { ctx._filters.push({ type: 'ilike', col, pattern }); return ctx }),
      single: vi.fn().mockReturnThis(),
      insert: vi.fn().mockImplementation((row: any) => { state.push(row); return ctx }),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      gte: vi.fn().mockReturnThis(),
      lte: vi.fn().mockReturnThis(),
      then: undefined,
      async execute() { return { data: state, error: null } },
      async _resolve(res: any) { return res },
    }

    // Return data based on final method in chain
    Object.defineProperty(ctx, 'data', { get: () => state })

    const handler = async () => ({ data: state, error: null })
    ctx.then = handler as any

    return new Proxy(ctx, {
      get(target, prop: string) {
        if (prop === 'then') return handler
        if (prop === 'select') return target.select
        if (prop === 'order') return target.order
        if (prop === 'eq') return target.eq
        if (prop === 'in') return target.in
        if (prop === 'ilike') return target.ilike
        if (prop === 'single') return target.single
        if (prop === 'insert') return target.insert
        if (prop === 'update') return target.update
        if (prop === 'delete') return target.delete
        if (prop === 'gte') return target.gte
        if (prop === 'lte') return target.lte
        return (target as any)[prop]
      },
      apply() { return handler() },
    })
  })

  return {
    from,
    state,
  } as any
}

describe('JobUseCases', () => {
  let mockSupabase: any
  let useCases: JobUseCases

  beforeEach(() => {
    mockSupabase = createMockSupabase()
    useCases = new JobUseCases(mockSupabase)
  })

  it('creates a job and lists jobs', async () => {
    const created = await useCases.createJob({ name: 'Test Job', status: 'draft' as any })
    expect(created).toBeDefined()

    const jobs = await useCases.fetchJobs()
    expect(Array.isArray(jobs)).toBe(true)
  })
})
