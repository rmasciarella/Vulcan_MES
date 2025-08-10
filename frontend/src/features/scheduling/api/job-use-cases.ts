import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import type { JobInstance } from '@/core/types/database'
import { JobsListFilters } from '../types'
// Simple error message extraction utility (replaced deprecated http-client import)
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return String(error)
}

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
 * Enhanced with comprehensive error handling and validation
 */
export class JobUseCases {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Validate job data before operations
   */
  private validateJobData(data: any, operation: string): void {
    if (!data) {
      throw new Error(`Invalid job data provided for ${operation}`)
    }
    if (operation === 'create' && !data.name) {
      throw new Error('Job name is required for creation')
    }
  }

  /**
   * Handle Supabase errors with context
   */
  private handleSupabaseError(error: any, operation: string, context?: string): never {
    const baseMessage = `Failed to ${operation} job${context ? ` ${context}` : ''}`
    
    if (error.code === 'PGRST116') {
      throw new Error(`${baseMessage}: Job not found`)
    }
    if (error.code === '23505') {
      throw new Error(`${baseMessage}: Job with this name already exists`)
    }
    if (error.code === '23503') {
      throw new Error(`${baseMessage}: Referenced resource does not exist`)
    }
    if (error.code === '23514') {
      throw new Error(`${baseMessage}: Invalid data provided`)
    }
    
    throw new Error(`${baseMessage}: ${getErrorMessage(error)}`)
  }

  /**
   * Fetch jobs with optional filtering and pagination
   */
  async getJobs(filters?: JobsListFilters): Promise<JobInstance[]> {
    try {
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
        const searchTerm = filters.search.trim()
        if (searchTerm) {
          query = query.ilike('name', `%${searchTerm}%`)
        }
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
        this.handleSupabaseError(error, 'fetch', 'list')
      }

      return (data as JobInstance[]) || []
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error(`Unexpected error fetching jobs: ${getErrorMessage(error)}`)
    }
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
    try {
      if (!id || typeof id !== 'string') {
        throw new Error('Valid job ID is required')
      }

      const { data, error } = await this.supabase
        .from('job_instances')
        .select('*')
        .eq('instance_id', id.trim())
        .single()

      if (error) {
        this.handleSupabaseError(error, 'fetch', `with ID ${id}`)
      }

      if (!data) {
        throw new Error(`Job with ID ${id} not found`)
      }

      return data as JobInstance
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error(`Unexpected error fetching job: ${getErrorMessage(error)}`)
    }
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
    try {
      this.validateJobData(jobData, 'create')

      const now = new Date().toISOString()
      const insertData = {
        name: jobData.name.trim(),
        status: jobData.status || 'draft',
        created_at: now,
        updated_at: now,
      }

      const { data, error } = await this.supabase
        .from('job_instances')
        .insert(insertData)
        .select()
        .single()

      if (error) {
        this.handleSupabaseError(error, 'create')
      }

      if (!data) {
        throw new Error('Job creation failed: No data returned')
      }

      return data as JobInstance
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error(`Unexpected error creating job: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Update an existing job
   */
  async updateJob(id: string, updateData: UpdateJobData): Promise<JobInstance> {
    try {
      if (!id || typeof id !== 'string') {
        throw new Error('Valid job ID is required')
      }
      if (!updateData || Object.keys(updateData).length === 0) {
        throw new Error('Update data is required')
      }

      const updates: any = {
        updated_at: new Date().toISOString(),
      }

      if (updateData.name !== undefined) {
        const trimmedName = updateData.name.trim()
        if (!trimmedName) {
          throw new Error('Job name cannot be empty')
        }
        updates.name = trimmedName
      }
      if (updateData.status !== undefined) {
        updates.status = updateData.status
      }

      const { data, error } = await this.supabase
        .from('job_instances')
        .update(updates)
        .eq('instance_id', id.trim())
        .select()
        .single()

      if (error) {
        this.handleSupabaseError(error, 'update', `with ID ${id}`)
      }

      if (!data) {
        throw new Error(`Job with ID ${id} not found for update`)
      }

      return data as JobInstance
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error(`Unexpected error updating job: ${getErrorMessage(error)}`)
    }
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
    try {
      if (!id || typeof id !== 'string') {
        throw new Error('Valid job ID is required')
      }

      const { error, count } = await this.supabase
        .from('job_instances')
        .delete({ count: 'exact' })
        .eq('instance_id', id.trim())

      if (error) {
        this.handleSupabaseError(error, 'delete', `with ID ${id}`)
      }

      if (count === 0) {
        throw new Error(`Job with ID ${id} not found for deletion`)
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error(`Unexpected error deleting job: ${getErrorMessage(error)}`)
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