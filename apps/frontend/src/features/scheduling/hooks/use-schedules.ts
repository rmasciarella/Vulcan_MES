import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
// TODO: Realtime migration: expose domain-friendly subscription API via UseCaseFactory. Avoid direct Supabase imports here.
import type { SolvedSchedule, SolvedScheduleInsert, ScheduledTask } from '@/core/types/database'
import type { ScheduleFilters } from '@/infrastructure/supabase/repositories/supabase-schedule-repository'
import { useUIStore } from '@/core/stores/ui-store'
import { useSchedulingStore } from '@/core/stores/scheduling-store'
import { SchedulingUseCaseFactory } from '../api/use-case-factory'
import { useEffect } from 'react'

// Use SolvedSchedule as Schedule type alias for consistency
type Schedule = SolvedSchedule

// Enhanced query keys factory for better caching strategy
export const scheduleKeys = {
  all: ['schedules'] as const,
  lists: () => [...scheduleKeys.all, 'list'] as const,
  list: (filters: ScheduleFilters) => [...scheduleKeys.lists(), filters] as const,
  details: () => [...scheduleKeys.all, 'detail'] as const,
  detail: (id: string) => [...scheduleKeys.details(), id] as const,
  tasks: (scheduleId: string) => [...scheduleKeys.detail(scheduleId), 'tasks'] as const,
  byStatus: (status: string) => [...scheduleKeys.all, 'status', status] as const,
  stats: () => [...scheduleKeys.all, 'stats'] as const,
}

// Fetch schedules with optional filters - now uses domain layer with DI
async function fetchSchedules(filters?: ScheduleFilters): Promise<Schedule[]> {
  const factory = SchedulingUseCaseFactory.getInstance()
  const scheduleUseCases = await factory.getScheduleUseCases()
  const result = await scheduleUseCases.fetchSchedules(filters)
  return result as Schedule[]
}

// TODO: Temporarily simplified until schedule use cases are properly migrated
async function fetchScheduleById(id: string): Promise<Schedule | null> {
  console.warn('Schedule API not implemented - returning null')
  return null
}

// TODO: Temporarily simplified until schedule use cases are properly migrated
async function fetchScheduleTasks(scheduleId: string): Promise<ScheduledTask[]> {
  console.warn('Schedule tasks API not implemented - returning empty array')
  return []
}

// Create a new schedule - now uses domain layer with DI
async function createSchedule(schedule: SolvedScheduleInsert): Promise<Schedule> {
  const factory = SchedulingUseCaseFactory.getInstance()
  const scheduleUseCases = await factory.getScheduleUseCases()
  const result = await scheduleUseCases.createSchedule(schedule)
  return result as Schedule
}

// TODO: Temporarily simplified until schedule use cases are properly migrated
async function updateScheduleSolverStatus({
  id,
  solverStatus,
}: {
  id: string
  solverStatus: string
}): Promise<Schedule> {
  console.warn('Update schedule solver status API not implemented')
  throw new Error('Schedule API not implemented')
}

// TODO: Temporarily simplified until schedule use cases are properly migrated
async function saveDraftSchedule({
  scheduleId,
  tasks,
}: {
  scheduleId: string
  tasks: ScheduledTask[]
}) {
  console.warn('Save draft schedule API not implemented')
  throw new Error('Schedule API not implemented')
}

// Enhanced hook to fetch schedules list with optional real-time updates
export function useSchedules(
  filters?: ScheduleFilters,
  options?: {
    enableRealtime?: boolean
    refetchInterval?: number
    staleTime?: number
  },
) {
  const queryClient = useQueryClient()
  const {
    enableRealtime = false,
    refetchInterval = enableRealtime ? (false as const) : 30 * 1000,
    staleTime = 30 * 1000,
  } = options || {}

  const query = useQuery({
    queryKey: scheduleKeys.list(filters || {}),
    queryFn: () => fetchSchedules(filters),
    staleTime,
    refetchInterval,
    refetchIntervalInBackground: enableRealtime,
  })

// Set up real-time subscription for schedule changes
  useEffect(() => {
    if (!enableRealtime) return

    // TODO: Realtime migration
    // We intentionally avoid importing Supabase client directly here.
    // Replace this with a domain-level event stream once available.
    // For now, rely on periodic refetch via React Query options above.
  }, [enableRealtime, filters?.solverStatus, queryClient])

  return query
}

// Enhanced hook to fetch single schedule with caching optimization
export function useSchedule(id: string, options?: { enableRealtime?: boolean }) {
  const { enableRealtime = false } = options || {}

  return useQuery({
    queryKey: scheduleKeys.detail(id),
    queryFn: () => fetchScheduleById(id),
    enabled: !!id,
    staleTime: enableRealtime ? 30 * 1000 : 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000, // 10 minutes cache retention
  })
}

// Hook to fetch schedule tasks
export function useScheduleTasks(scheduleId: string) {
  return useQuery({
    queryKey: scheduleKeys.tasks(scheduleId),
    queryFn: () => fetchScheduleTasks(scheduleId),
    enabled: !!scheduleId,
    staleTime: 30 * 1000, // 30 seconds
  })
}

// Enhanced hook to create schedule with optimistic updates
export function useCreateSchedule() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: createSchedule,
    onSuccess: (newSchedule) => {
      // Add to cache and invalidate lists
      queryClient.setQueryData(scheduleKeys.detail(newSchedule.id), newSchedule)
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.stats() })
      
      // Invalidate status-specific queries if schedule has status
      if (newSchedule.status) {
        queryClient.invalidateQueries({ queryKey: scheduleKeys.byStatus(newSchedule.status) })
      }

      addNotification({
        type: 'success',
        title: 'Schedule Created',
        message: `Schedule created successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Creation Failed',
        message: error.message,
      })
    },
  })
}

// Enhanced hook to update schedule solver status with optimistic updates
export function useUpdateScheduleSolverStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: updateScheduleSolverStatus,
    onMutate: async ({ id, solverStatus }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: scheduleKeys.detail(id) })

      // Snapshot the previous value
      const previousSchedule = queryClient.getQueryData(scheduleKeys.detail(id))

      // Optimistically update the schedule status
      if (previousSchedule) {
        queryClient.setQueryData(scheduleKeys.detail(id), {
          ...previousSchedule,
          status: solverStatus,
          updated_at: new Date().toISOString(),
        })
      }

      return { previousSchedule }
    },
    onSuccess: (data, { solverStatus }) => {
      // Update the specific schedule in cache with server response
      queryClient.setQueryData(scheduleKeys.detail(data.id), data)
      
      // Only invalidate queries that depend on solver status
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.byStatus(solverStatus) })
      
      // If status changed from previous status, invalidate old status queries too
      const previousSchedule = queryClient.getQueryData(scheduleKeys.detail(data.id)) as Schedule | undefined
      if (previousSchedule?.status && previousSchedule.status !== solverStatus) {
        queryClient.invalidateQueries({ queryKey: scheduleKeys.byStatus(previousSchedule.status) })
      }

      addNotification({
        type: 'success',
        title: 'Schedule Updated',
        message: `Schedule solver status changed to ${data.status}`,
      })
    },
    onError: (error, { id }, context) => {
      // Rollback optimistic update
      if (context?.previousSchedule) {
        queryClient.setQueryData(scheduleKeys.detail(id), context.previousSchedule)
      }

      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.message,
      })
    },
    onSettled: (_, __, { id }) => {
      // Always refetch after mutation to ensure consistency
      queryClient.invalidateQueries({ queryKey: scheduleKeys.detail(id) })
    },
  })
}

// Enhanced hook to save draft schedule with better feedback
export function useSaveDraftSchedule() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)
  const clearDraftSchedule = useSchedulingStore((state) => state.clearDraftSchedule)

  return useMutation({
    mutationFn: saveDraftSchedule,
    onSuccess: (data) => {
      // Only invalidate queries directly related to this schedule
      queryClient.invalidateQueries({ queryKey: scheduleKeys.tasks(data.scheduleId) })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.detail(data.scheduleId) })
      clearDraftSchedule()

      addNotification({
        type: 'success',
        title: 'Schedule Saved',
        message: `${data.taskCount} tasks saved successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Save Failed',
        message: error.message,
      })
    },
  })
}

// Hook to delete a schedule
export function useDeleteSchedule() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (id: string) => {
      console.warn('Delete schedule API not implemented')
      throw new Error('Schedule API not implemented')
    },
    onSuccess: (_, deletedId) => {
      // Get schedule data before removing to optimize invalidations
      const deletedSchedule = queryClient.getQueryData(scheduleKeys.detail(deletedId)) as Schedule | undefined
      
      // Remove from cache
      queryClient.removeQueries({ queryKey: scheduleKeys.detail(deletedId) })
      queryClient.removeQueries({ queryKey: scheduleKeys.tasks(deletedId) })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.lists() })
      queryClient.invalidateQueries({ queryKey: scheduleKeys.stats() })

      // Only invalidate status-specific queries if we know the status
      if (deletedSchedule?.status) {
        queryClient.invalidateQueries({ queryKey: scheduleKeys.byStatus(deletedSchedule.status) })
      }

      addNotification({
        type: 'success',
        title: 'Schedule Deleted',
        message: 'Schedule has been deleted successfully',
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Schedule Failed',
        message: error.message,
      })
    },
  })
}

// Hook to fetch schedules by status for dashboard components
export function useSchedulesByStatus(status: string, enableRealtime = true) {
  return useQuery({
    queryKey: scheduleKeys.byStatus(status),
    queryFn: () => fetchSchedules({ solverStatus: status }),
    staleTime: enableRealtime ? 15 * 1000 : 60 * 1000,
    refetchInterval: enableRealtime ? (false as const) : 30 * 1000,
    refetchIntervalInBackground: false,
  })
}

// Hook for real-time schedule monitoring
export function useScheduleRealtime(scheduleId: string) {
  // TODO: Realtime migration: replace with domain-level event stream. For now, just use the regular hook.
  return useSchedule(scheduleId)
}

// Export types for external use
export type { ScheduleFilters }
