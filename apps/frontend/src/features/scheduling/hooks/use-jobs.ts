import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import type { Tables } from '@/types/supabase'
import { useUIStore } from '@/core/stores/ui-store'
import { SchedulingUseCaseFactory } from '../api/use-case-factory'
import type { JobsListFilters } from '../types'

type JobInstance = Tables<'job_instances'>
type JobStatus = JobInstance['status']

// Enhanced query keys factory for better caching strategy
export const jobKeys = {
  all: ['jobs'] as const,
  lists: () => [...jobKeys.all, 'list'] as const,
  list: (filters: JobsListFilters) => [...jobKeys.lists(), filters] as const,
  infinite: (filters: JobsListFilters) => [...jobKeys.lists(), 'infinite', filters] as const,
  details: () => [...jobKeys.all, 'detail'] as const,
  detail: (id: string) => [...jobKeys.details(), id] as const,
  byStatus: (status: JobStatus) => [...jobKeys.all, 'status', status] as const,
  byTemplate: (templateId: string) => [...jobKeys.all, 'template', templateId] as const,
  byDateRange: (startDate: string, endDate: string) =>
    [...jobKeys.all, 'dateRange', startDate, endDate] as const,
  stats: () => [...jobKeys.all, 'stats'] as const,
  count: () => [...jobKeys.all, 'count'] as const,
}

// Enhanced fetch jobs with comprehensive filtering - uses domain layer with DI
async function fetchJobs(filters?: JobsListFilters) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobs(filters)
}

// Fetch jobs with pagination for large datasets
async function fetchJobsPaginated(pageParam: number, filters?: JobsListFilters, pageSize = 50) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobsPaginated(pageSize, pageParam * pageSize)
}

// Fetch job statistics for dashboard
async function fetchJobStats() {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.getJobCount()
}

// Fetch jobs by status for manufacturing dashboards
async function fetchJobsByStatus(status: JobStatus) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobs({ status })
}

// Fetch jobs by template for batch operations
async function fetchJobsByTemplate(templateId: string) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobsByTemplateId(templateId)
}

// Fetch jobs by due date range for scheduling
async function fetchJobsByDateRange(startDate: Date, endDate: Date) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobsByDueDateRange(startDate, endDate)
}

// Fetch single job by ID - now uses domain layer with DI
async function fetchJobById(id: string) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.fetchJobById(id)
}

// Update job status - now uses domain layer with validation and DI
async function updateJobStatus({ id, status }: { id: string; status: JobStatus }) {
  const factory = SchedulingUseCaseFactory.getInstance()
  const jobUseCases = await factory.getJobUseCases()
  return await jobUseCases.updateJobStatus({ id, status })
}

// Utilities are colocated in a dependency-free helpers module for testability
import { isJobsListKey, normalizeStatusFilter, listKeyMatchesStatus } from './use-jobs-helpers'

// Enhanced hook to fetch jobs list with real-time updates
export function useJobs(
  filters?: JobsListFilters,
  options?: {
    enableRealtime?: boolean
    refetchInterval?: number
    staleTime?: number
  },
) {
  const queryClient = useQueryClient()
  const {
    enableRealtime = false,
    // Set safety fallback of 10 minutes when realtime is enabled; otherwise default to 30s
    refetchInterval = enableRealtime ? 10 * 60 * 1000 : 30 * 1000,
    staleTime = 30 * 1000,
  } = options || {}

  const query = useQuery({
    queryKey: jobKeys.list(filters || {}),
    queryFn: () => fetchJobs(filters),
    staleTime,
    refetchInterval,
    // Do not refetch in background when realtime is enabled
    refetchIntervalInBackground: !enableRealtime,
  })

  // Set up real-time subscription for job changes
  useEffect(() => {
    if (!enableRealtime) return

    // TODO: Realtime migration
    // We intentionally avoid importing Supabase client directly here.
    // Replace this with a domain-level event stream once available.
    // For now, rely on periodic refetch per options.
  }, [enableRealtime, queryClient, JSON.stringify(filters)])

  return query
}

// Hook for infinite scrolling with virtualization support
export function useJobsInfinite(filters?: JobsListFilters, pageSize = 50) {
  const _queryClient = useQueryClient()

  return useInfiniteQuery({
    queryKey: jobKeys.infinite(filters || {}),
    queryFn: ({ pageParam = 0 }) => fetchJobsPaginated(pageParam, filters, pageSize),
    getNextPageParam: (lastPage, allPages) => {
      return lastPage.hasMore ? allPages.length : undefined
    },
    initialPageParam: 0,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000, // 5 minutes cache for performance
  })
}

// Enhanced hook to fetch single job with caching optimization
export function useJob(id: string, options?: { enableRealtime?: boolean }) {
  const { enableRealtime = false } = options || {}

  return useQuery({
    queryKey: jobKeys.detail(id),
    queryFn: () => fetchJobById(id),
    enabled: !!id,
    staleTime: enableRealtime ? 30 * 1000 : 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000, // 10 minutes cache retention
  })
}

// Enhanced hook to update job status with optimistic updates
export function useUpdateJobStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: updateJobStatus,
    onMutate: async ({ id, status }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: jobKeys.detail(id) })

      // Snapshot the previous value
      const previousJob = queryClient.getQueryData(jobKeys.detail(id))

      // Optimistically update the job status
      if (previousJob) {
        queryClient.setQueryData(jobKeys.detail(id), {
          ...previousJob,
          status,
          updated_at: new Date().toISOString(),
        })
      }

      return { previousJob }
    },
    onSuccess: (data) => {
      // Update the specific job in cache with server response
      queryClient.setQueryData(jobKeys.detail(data.instance_id), data)

      // Invalidate related queries for consistency (narrowed)
      queryClient.invalidateQueries({
        predicate: (q) => isJobsListKey(q.queryKey) && listKeyMatchesStatus(q.queryKey as readonly unknown[], data.status),
      })
      queryClient.invalidateQueries({ queryKey: jobKeys.stats() })
      queryClient.invalidateQueries({ queryKey: jobKeys.byStatus(data.status) })

      addNotification({
        type: 'success',
        title: 'Job Updated',
        message: `Job ${data.name} status changed to ${data.status}`,
      })
    },
    onError: (error, { id }, context) => {
      // Rollback optimistic update
      if (context?.previousJob) {
        queryClient.setQueryData(jobKeys.detail(id), context.previousJob)
      }

      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.message,
      })
    },
    onSettled: (_, __, { id }) => {
      // Always refetch after mutation to ensure consistency
      queryClient.invalidateQueries({ queryKey: jobKeys.detail(id) })
    },
  })
}

// Hook to create a new job
export function useCreateJob() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (data: {
      name: string
      status?: string
    }) => {
      const factory = SchedulingUseCaseFactory.getInstance()
      const jobUseCases = await factory.getJobUseCases()
      return await jobUseCases.createJob(data)
    },
    onSuccess: (newJob) => {
      // Add to cache and invalidate lists
      queryClient.setQueryData(jobKeys.detail(newJob.instance_id), newJob)
      // Invalidate only relevant queries for the new job
      queryClient.invalidateQueries({
        predicate: (q) => isJobsListKey(q.queryKey) && listKeyMatchesStatus(q.queryKey as readonly unknown[], newJob.status),
      })
      queryClient.invalidateQueries({ queryKey: jobKeys.stats() })
      queryClient.invalidateQueries({ queryKey: jobKeys.byStatus(newJob.status) })
      
      // Invalidate count query which aggregates all jobs
      queryClient.invalidateQueries({ queryKey: jobKeys.count() })

      addNotification({
        type: 'success',
        title: 'Job Created',
        message: `Job ${newJob.name} has been created successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Create Job Failed',
        message: error.message,
      })
    },
  })
}

// Hook to delete a job
export function useDeleteJob() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (id: string) => {
      const factory = SchedulingUseCaseFactory.getInstance()
      const jobUseCases = await factory.getJobUseCases()
      return await jobUseCases.deleteJob(id)
    },
    onSuccess: (_, deletedId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: jobKeys.detail(deletedId) })
      // Invalidate all jobs list queries (status unknown post-deletion)
      queryClient.invalidateQueries({ predicate: (q) => isJobsListKey(q.queryKey) })
      queryClient.invalidateQueries({ queryKey: jobKeys.stats() })

      addNotification({
        type: 'success',
        title: 'Job Deleted',
        message: 'Job has been deleted successfully',
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Job Failed',
        message: error.message,
      })
    },
  })
}

// Specialized hooks for dashboard components
export function useJobsByStatus(status: JobStatus, enableRealtime = true) {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: jobKeys.byStatus(status),
    queryFn: () => fetchJobsByStatus(status),
    staleTime: enableRealtime ? 15 * 1000 : 60 * 1000,
    // Set safety fallback of 10 minutes when realtime is enabled
    refetchInterval: enableRealtime ? 10 * 60 * 1000 : 30 * 1000,
    refetchIntervalInBackground: !enableRealtime,
  })

  // TODO: Realtime migration: avoid direct Supabase subscription here. Rely on polling until domain events are available.

  return query
}

export function useJobsByTemplate(templateId: string) {
  return useQuery({
    queryKey: jobKeys.byTemplate(templateId),
    queryFn: () => fetchJobsByTemplate(templateId),
    enabled: !!templateId,
    staleTime: 60 * 1000,
  })
}

export function useJobsByDateRange(startDate: Date, endDate: Date) {
  return useQuery({
    queryKey: jobKeys.byDateRange(startDate.toISOString(), endDate.toISOString()),
    queryFn: () => fetchJobsByDateRange(startDate, endDate),
    enabled: !!startDate && !!endDate,
    staleTime: 60 * 1000,
  })
}

export function useJobStats() {
  return useQuery({
    queryKey: jobKeys.stats(),
    queryFn: fetchJobStats,
    staleTime: 5 * 60 * 1000, // 5 minutes for stats
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
  })
}

// Hook for real-time job monitoring with WebSocket-like behavior
export function useJobRealtime(jobId: string) {
  const queryClient = useQueryClient()
  const query = useJob(jobId)

  // TODO: Realtime migration: avoid direct Supabase subscription here. Rely on query invalidations for now.

  return query
}

// Bulk operations hooks for manufacturing efficiency
export function useBulkUpdateJobStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (updates: Array<{ id: string; status: JobStatus }>) => {
      const factory = SchedulingUseCaseFactory.getInstance()
      const jobUseCases = await factory.getJobUseCases()

      // Process updates in parallel for performance
      const results = await Promise.allSettled(
        updates.map(({ id, status }) => jobUseCases.updateJobStatus({ id, status })),
      )

      return results
    },
    onSuccess: (results) => {
      const successful = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.filter((r) => r.status === 'rejected').length

      // Invalidate lists and stats for consistency without nuking all queries
      queryClient.invalidateQueries({ predicate: (q) => isJobsListKey(q.queryKey) })
      queryClient.invalidateQueries({ queryKey: jobKeys.stats() })

      addNotification({
        type: successful > 0 ? 'success' : 'error',
        title: 'Bulk Update Complete',
        message: `${successful} jobs updated successfully${failed > 0 ? `, ${failed} failed` : ''}`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Bulk Update Failed',
        message: error.message,
      })
    },
  })
}