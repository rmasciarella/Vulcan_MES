import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import type { JobInstance } from '@/core/types/database'
import { JobsListFilters } from '../types'

type JobStatus = JobInstance['status']

/**
 * Job creation data structure
 */
export interface CreateJobData {
  name: string
  status?: JobStatus
}

/**
 * Job update data structure  
 */
export interface UpdateJobData {
  name?: string
  status?: JobStatus
}

/**
 * Job statistics data structure
 */
export interface JobStats {
  total: number
  [key: string]: number  // Allow for dynamic status counts
}

/**
 * Paginated jobs response
 */
export interface PaginatedJobsResponse {
  data: JobInstance[]
  hasMore: boolean
  total: number
  page: number
  pageSize: number
}

/**
 * Business logic layer for job operations
 * Encapsulates all job-related use cases and domain logic
 */
export class JobUseCases {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Fetch jobs with optional filtering and pagination
   */
  async getJobs(filters?: JobsListFilters): Promise<JobInstance[]> {
    let query = this.supabase
      .from('job_instances')
      .select('*')
      .order('created_at', { ascending: false })

    // Apply status filter (single status or array)
    if (filters?.status) {
      if (Array.isArray(filters.status)) {
        query = query.in('status', filters.status)
      } else {
        query = query.eq('status', filters.status)
      }
    }

    // Apply search filter on name
    if (filters?.search) {
      query = query.ilike('name', `%${filters.search}%`)
    }

    // Apply sorting
    if (filters?.sortBy && filters?.sortOrder) {
      const ascending = filters.sortOrder === 'asc'
      switch (filters.sortBy) {
        case 'serialNumber':
          query = query.order('name', { ascending }) // Using name as serialNumber
          break
        case 'status':
          query = query.order('status', { ascending })
          break
        case 'createdAt':
          query = query.order('created_at', { ascending })
          break
        default:
          // Default sorting by created_at desc
          break
      }
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch jobs: ${error.message}`)
    }

    return data as JobInstance[]
  }

  /**
   * Fetch jobs with pagination support
   */
  async fetchJobsPaginated(
    pageSize: number = 50, 
    offset: number = 0, 
    filters?: JobsListFilters
  ): Promise<PaginatedJobsResponse> {
    // Get total count for pagination metadata
    let countQuery = this.supabase
      .from('job_instances')
      .select('*', { count: 'exact', head: true })

    // Apply same filters for count
    if (filters?.status) {
      if (Array.isArray(filters.status)) {
        countQuery = countQuery.in('status', filters.status)
      } else {
        countQuery = countQuery.eq('status', filters.status)
      }
    }
    if (filters?.search) {
      countQuery = countQuery.ilike('name', `%${filters.search}%`)
    }

    const { count, error: countError } = await countQuery

    if (countError) {
      throw new Error(`Failed to count jobs: ${countError.message}`)
    }

    // Get paginated data
    const jobs = await this.getJobs(filters)
    const paginatedJobs = jobs.slice(offset, offset + pageSize)

    return {
      data: paginatedJobs,
      hasMore: offset + pageSize < jobs.length,
      total: count || 0,
      page: Math.floor(offset / pageSize),
      pageSize,
    }
  }

  /**
   * Fetch a single job by ID
   */
  async getJob(id: string): Promise<JobInstance> {
    const { data, error } = await this.supabase
      .from('job_instances')
      .select('*')
      .eq('instance_id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        throw new Error(`Job with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch job: ${error.message}`)
    }

    return data as JobInstance
  }

  /**
   * Legacy method for backward compatibility with existing use-jobs.ts
   */
  async fetchJobs(filters?: JobsListFilters): Promise<JobInstance[]> {
    return this.getJobs(filters)
  }

  /**
   * Legacy method for backward compatibility with existing use-jobs.ts
   */
  async fetchJobById(id: string): Promise<JobInstance> {
    return this.getJob(id)
  }

  /**
   * Legacy method for backward compatibility - simplified for current schema
   */
  async fetchJobsByTemplateId(templateId: string): Promise<JobInstance[]> {
    // Since template_id doesn't exist in current schema, return all jobs
    // This maintains compatibility while the schema is being evolved
    return this.getJobs()
  }

  /**
   * Legacy method for backward compatibility - simplified for current schema
   */
  async fetchJobsByDueDateRange(startDate: Date, endDate: Date): Promise<JobInstance[]> {
    // Since due_date doesn't exist in current schema, return all jobs
    // This maintains compatibility while the schema is being evolved
    return this.getJobs()
  }

  /**
   * Create a new job
   */
  async createJob(jobData: CreateJobData): Promise<JobInstance> {
    const { data, error } = await this.supabase
      .from('job_instances')
      .insert({
        name: jobData.name,
        status: jobData.status || 'draft',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to create job: ${error.message}`)
    }

    return data as JobInstance
  }

  /**
   * Update an existing job
   */
  async updateJob(id: string, updateData: UpdateJobData): Promise<JobInstance> {
    const updates: any = {
      updated_at: new Date().toISOString(),
    }

    if (updateData.name !== undefined) updates.name = updateData.name
    if (updateData.status !== undefined) updates.status = updateData.status

    const { data, error } = await this.supabase
      .from('job_instances')
      .update(updates)
      .eq('instance_id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update job: ${error.message}`)
    }

    return data as JobInstance
  }

  /**
   * Update job status - specialized method used by hooks
   */
  async updateJobStatus({ id, status }: { id: string; status: JobStatus }): Promise<JobInstance> {
    return this.updateJob(id, { status })
  }

  /**
   * Delete a job
   */
  async deleteJob(id: string): Promise<void> {
    const { error } = await this.supabase
      .from('job_instances')
      .delete()
      .eq('instance_id', id)

    if (error) {
      throw new Error(`Failed to delete job: ${error.message}`)
    }
  }

  /**
   * Bulk update job statuses
   */
  async bulkUpdateStatus(updates: Array<{ id: string; status: JobStatus }>): Promise<JobInstance[]> {
    const results = await Promise.allSettled(
      updates.map(({ id, status }) => this.updateJobStatus({ id, status }))
    )

    const successful = results
      .filter((result): result is PromiseFulfilledResult<JobInstance> => result.status === 'fulfilled')
      .map(result => result.value)

    const failed = results.filter(result => result.status === 'rejected')

    if (failed.length > 0) {
      console.warn(`${failed.length} job status updates failed:`, failed)
    }

    return successful
  }

  /**
   * Get job count statistics for analytics/dashboard
   */
  async getJobCount(): Promise<JobStats> {
    const { data: jobs, error } = await this.supabase
      .from('job_instances')
      .select('status')

    if (error) {
      throw new Error(`Failed to get job counts: ${error.message}`)
    }

    const statusCounts = (jobs || []).reduce((acc, job) => {
      const status = job.status || 'draft'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    return {
      total: jobs?.length || 0,
      ...statusCounts,
    }
  }

  /**
   * Get jobs by status
   */
  async getJobsByStatus(status: JobStatus): Promise<JobInstance[]> {
    return this.getJobs({ status })
  }

  /**
   * Search jobs by name
   */
  async searchJobs(searchTerm: string): Promise<JobInstance[]> {
    return this.getJobs({ search: searchTerm })
  }
}