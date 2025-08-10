import { useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useJobSchedulingStore } from '../stores/job-scheduling-store'
import { useJobs, useCreateJob, useUpdateJobStatus, jobKeys } from '../../scheduling/hooks/use-jobs'
import { useUIStore } from '@/core/stores/ui-store'
import type { JobPriority, JobStatusValue } from '../../scheduling/types/jobs'
import type { JobSchedulingFilters } from '../stores/job-scheduling-store'

// Custom hook for managing job scheduling state
export function useJobScheduling() {
  const {
    currentView,
    selectedJobs,
    filters,
    isDragging,
    draggedJobId,
    schedulingDraft,
    preferences,
    setView,
    setFilters,
    toggleJobSelection,
    selectAllJobs,
    clearSelection,
    startDragging,
    stopDragging,
    updateJobSchedule,
    removeJobFromSchedule,
    clearSchedulingDraft,
    updatePreferences,
  } = useJobSchedulingStore()

  return {
    // State
    currentView,
    selectedJobs,
    filters,
    isDragging,
    draggedJobId,
    schedulingDraft,
    preferences,
    
    // Actions
    setView,
    setFilters,
    toggleJobSelection,
    selectAllJobs,
    clearSelection,
    startDragging,
    stopDragging,
    updateJobSchedule,
    removeJobFromSchedule,
    clearSchedulingDraft,
    updatePreferences,
  }
}

// Hook for fetching jobs with scheduling-specific filters
export function useJobsForScheduling(additionalFilters?: Partial<JobSchedulingFilters>) {
  const { filters } = useJobSchedulingStore()
  
  // Convert priority to API-compatible format
  const apiPriority: 'high' | 'medium' | 'low' | undefined = filters.priority !== undefined ? (
    filters.priority === 'critical' ? 'high' as const : 
    filters.priority === 'high' ? 'high' as const :
    filters.priority === 'medium' ? 'medium' as const :
    filters.priority === 'low' ? 'low' as const : 
    undefined
  ) : undefined

  // Destructure filters to exclude priority which we handle separately
  const { priority: _, ...filtersWithoutPriority } = filters
  
  // Also exclude priority from additionalFilters
  const { priority: _2, ...additionalFiltersWithoutPriority } = additionalFilters || {}
  
  const combinedFilters = {
    ...filtersWithoutPriority,
    ...additionalFiltersWithoutPriority,
    // Convert to scheduling API format
    ...(apiPriority !== undefined && { priority: apiPriority }),
    ...(filters.search !== undefined && { search: filters.search }),
    ...(filters.dateRange?.start && { dueDateStart: filters.dateRange.start.toISOString().split('T')[0] }),
    ...(filters.dateRange?.end && { dueDateEnd: filters.dateRange.end.toISOString().split('T')[0] }),
  }

  return useJobs(combinedFilters, {
    enableRealtime: true,
    staleTime: 30 * 1000,
  })
}

// Hook for scheduling jobs in batch
export function useBatchScheduleJobs() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)
  const { clearSchedulingDraft, schedulingDraft } = useJobSchedulingStore()

  return useMutation({
    mutationFn: async (scheduleData: {
      jobs: Array<{
        jobId: string
        scheduledStartDate?: Date
        scheduledEndDate?: Date
        priority?: JobPriority
      }>
    }) => {
      // In a real implementation, this would call a batch scheduling API
      // For now, we'll simulate the operation
      await new Promise(resolve => setTimeout(resolve, 1000))
      return { scheduledJobs: scheduleData.jobs.length }
    },
    onSuccess: (result) => {
      // Clear the draft after successful scheduling
      clearSchedulingDraft()
      
      // Invalidate jobs queries to refresh the UI
      queryClient.invalidateQueries({ 
        predicate: (query) => query.queryKey[0] === 'jobs'
      })

      addNotification({
        type: 'success',
        title: 'Jobs Scheduled',
        message: `${result.scheduledJobs} jobs have been scheduled successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Scheduling Failed',
        message: error.message || 'Failed to schedule jobs',
      })
    },
  })
}

// Hook for auto-scheduling jobs based on constraints
export function useAutoScheduleJobs() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (jobIds: string[]) => {
      // In a real implementation, this would call the auto-scheduling service
      // which uses OR-Tools CP-SAT solver for optimization
      await new Promise(resolve => setTimeout(resolve, 2000))
      return { scheduledJobs: jobIds.length, optimizationScore: 0.85 }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ 
        predicate: (query) => query.queryKey[0] === 'jobs'
      })

      addNotification({
        type: 'success',
        title: 'Auto-Scheduling Complete',
        message: `${result.scheduledJobs} jobs auto-scheduled with ${Math.round(result.optimizationScore * 100)}% optimization`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Auto-Scheduling Failed',
        message: error.message || 'Failed to auto-schedule jobs',
      })
    },
  })
}

// Hook for reordering jobs by priority
export function useReorderJobsPriority() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (reorderData: Array<{ jobId: string; newPriority: JobPriority }>) => {
      // In a real implementation, this would update job priorities
      await new Promise(resolve => setTimeout(resolve, 500))
      return reorderData
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ 
        predicate: (query) => query.queryKey[0] === 'jobs'
      })

      addNotification({
        type: 'success',
        title: 'Priority Updated',
        message: `${result.length} jobs priority updated successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Priority Update Failed',
        message: error.message || 'Failed to update job priorities',
      })
    },
  })
}

// Hook for scheduling conflicts detection
export function useSchedulingConflicts() {
  const { schedulingDraft } = useJobSchedulingStore()

  const detectConflicts = useCallback(() => {
    // Simple conflict detection logic
    const conflicts: Array<{
      jobId: string
      conflictType: 'resource' | 'time' | 'dependency'
      description: string
    }> = []

    // Check for time overlaps
    for (let i = 0; i < schedulingDraft.jobs.length; i++) {
      for (let j = i + 1; j < schedulingDraft.jobs.length; j++) {
        const job1 = schedulingDraft.jobs[i]
        const job2 = schedulingDraft.jobs[j]
        
        if (job1 && job2 && 
            job1.scheduledStartDate && job1.scheduledEndDate && 
            job2.scheduledStartDate && job2.scheduledEndDate) {
          
          const overlap = (job1.scheduledStartDate < job2.scheduledEndDate) &&
                          (job2.scheduledStartDate < job1.scheduledEndDate)
          
          if (overlap) {
            conflicts.push({
              jobId: job1.jobId,
              conflictType: 'time',
              description: `Time conflict with job ${job2.jobId}`,
            })
          }
        }
      }
    }

    return conflicts
  }, [schedulingDraft.jobs])

  return {
    conflicts: detectConflicts(),
    hasConflicts: detectConflicts().length > 0,
  }
}

// Hook for managing job scheduling preferences
export function useJobSchedulingPreferences() {
  const { preferences, updatePreferences } = useJobSchedulingStore()

  const toggleAutoSchedule = useCallback(() => {
    updatePreferences({ autoSchedule: !preferences.autoSchedule })
  }, [preferences.autoSchedule, updatePreferences])

  const toggleShowDependencies = useCallback(() => {
    updatePreferences({ showDependencies: !preferences.showDependencies })
  }, [preferences.showDependencies, updatePreferences])

  const toggleGroupByPriority = useCallback(() => {
    updatePreferences({ groupByPriority: !preferences.groupByPriority })
  }, [preferences.groupByPriority, updatePreferences])

  const setTimeScale = useCallback((timeScale: 'hours' | 'days' | 'weeks') => {
    updatePreferences({ timeScale })
  }, [updatePreferences])

  return {
    preferences,
    toggleAutoSchedule,
    toggleShowDependencies,
    toggleGroupByPriority,
    setTimeScale,
  }
}