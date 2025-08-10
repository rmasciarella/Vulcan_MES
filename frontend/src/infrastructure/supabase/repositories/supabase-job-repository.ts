import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '@/types/supabase'

export interface ProductionJobRow {
  id?: string
  created_at?: string
  updated_at?: string
  status?: string
  name?: string
  customer_id?: string
  due_date?: string
  priority?: number
  serial_number?: string
  product_type?: string
  template_id?: string
  // Add any additional columns you care about as you iterate
  [key: string]: any
}

export interface JobWithTasks extends ProductionJobRow {
  tasks?: Array<{
    id: string
    name: string
    status: string
    sequence_number: number
    [key: string]: any
  }>
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  hasMore: boolean
}

export class SupabaseJobRepository {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  async listRecent(limit = 10): Promise<ProductionJobRow[]> {
    const { data, error } = await this.supabase
      .from('production_jobs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) throw new Error(`listRecent failed: ${error.message}`)
    return data ?? []
  }

  async findByIdsWithBatchLoading(jobIds: string[]): Promise<ProductionJobRow[]> {
    if (jobIds.length === 0) {
      return []
    }

    const { data, error } = await this.supabase
      .from('production_jobs')
      .select('*')
      .in('id', jobIds)
      .order('created_at', { ascending: false })

    if (error) throw new Error(`findByIdsWithBatchLoading failed: ${error.message}`)
    return data ?? []
  }

  async bulkSave(jobs: ProductionJobRow[]): Promise<ProductionJobRow[]> {
    if (jobs.length === 0) {
      return []
    }

    const { data, error } = await this.supabase
      .from('production_jobs')
      .upsert(jobs)
      .select()

    if (error) throw new Error(`bulkSave failed: ${error.message}`)
    return data ?? []
  }

  async count(): Promise<number> {
    const { count, error } = await this.supabase
      .from('production_jobs')
      .select('*', { count: 'exact', head: true })

    if (error) throw new Error(`count failed: ${error.message}`)
    return count ?? 0
  }

  async countByStatusAndDateRange(
    status: string,
    startDate: Date,
    endDate: Date
  ): Promise<number> {
    const { count, error } = await this.supabase
      .from('production_jobs')
      .select('*', { count: 'exact', head: true })
      .eq('status', status)
      .gte('created_at', startDate.toISOString())
      .lte('created_at', endDate.toISOString())

    if (error) throw new Error(`countByStatusAndDateRange failed: ${error.message}`)
    return count ?? 0
  }

  async findByStatusWithOptionalTasks(status: string, includeTasks: boolean = false): Promise<JobWithTasks[]> {
    const selectClause = includeTasks 
      ? `*, tasks(id, name, status, sequence_number)`
      : '*'

    const { data, error } = await this.supabase
      .from('production_jobs')
      .select(selectClause)
      .eq('status', status)
      .order('created_at', { ascending: false })

    if (error) throw new Error(`findByStatusWithOptionalTasks failed: ${error.message}`)
    return data ?? []
  }

  async findPaginated(
    limit: number,
    offset: number,
    filters?: { status?: string; customer_id?: string }
  ): Promise<PaginatedResult<ProductionJobRow>> {
    let query = this.supabase
      .from('production_jobs')
      .select('*', { count: 'exact' })
      .range(offset, offset + limit - 1)
      .order('created_at', { ascending: false })

    if (filters?.status) {
      query = query.eq('status', filters.status)
    }

    if (filters?.customer_id) {
      query = query.eq('customer_id', filters.customer_id)
    }

    const { data, error, count } = await query

    if (error) throw new Error(`findPaginated failed: ${error.message}`)
    
    const total = count ?? 0
    const hasMore = offset + limit < total

    return {
      data: data ?? [],
      total,
      hasMore
    }
  }
}
