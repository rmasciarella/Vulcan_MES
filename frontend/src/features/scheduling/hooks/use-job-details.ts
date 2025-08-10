import { useCallback } from 'react'
import {
  useJob,
  useJobRealtime,
  useUpdateJobStatus,
  useDeleteJob,
} from './use-jobs'
import { useTasks } from './use-tasks'
import type { JobInstance } from '@/types/supabase'

// Using direct JobInstance type from supabase types
type JobStatus = JobInstance['status']

interface UseJobDetailsDataOptions {
  jobId: string
  enableRealtime?: boolean
}

interface JobStatusTransition {
  status: JobStatus
  label: string
  icon: React.ComponentType
}

/**
 * Custom hook for job details data fetching
 * Consolidates realtime vs static job queries and related tasks
 */
export function useJobDetailsData({ jobId, enableRealtime = true }: UseJobDetailsDataOptions) {
  // Use real-time hook for live updates if enabled
  const realtimeJobQuery = useJobRealtime(jobId)
  const staticJobQuery = useJob(jobId)
  const jobQuery = enableRealtime ? realtimeJobQuery : staticJobQuery
  const { data: job, isLoading, isError, error } = jobQuery

  // Get related tasks for this job
  const { data: tasks, isLoading: tasksLoading } = useTasks({ jobId })

  return {
    job,
    tasks,
    isLoading,
    isError,
    error,
    tasksLoading,
    refetch: jobQuery.refetch,
  }
}

/**
 * Custom hook for job status transitions business logic
 * Extracts the complex business rules for status changes
 */
export function useJobStatusTransitions(job: JobInstance | undefined) {
  const getAvailableTransitions = useCallback((): JobStatusTransition[] => {
    if (!job) return []

    const transitions: JobStatusTransition[] = []

    // Import icons dynamically to avoid circular dependencies
    const { Calendar, Play, Pause, CheckCircle2, XCircle } = require('lucide-react')

    switch (job.status) {
      case 'DRAFT':
        transitions.push({ status: 'SCHEDULED', label: 'Schedule', icon: Calendar })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
      case 'SCHEDULED':
        transitions.push({ status: 'IN_PROGRESS', label: 'Start', icon: Play })
        transitions.push({ status: 'ON_HOLD', label: 'Hold', icon: Pause })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
      case 'IN_PROGRESS':
        transitions.push({ status: 'COMPLETED', label: 'Complete', icon: CheckCircle2 })
        transitions.push({ status: 'ON_HOLD', label: 'Hold', icon: Pause })
        break
      case 'ON_HOLD':
        transitions.push({ status: 'IN_PROGRESS', label: 'Resume', icon: Play })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
    }

    return transitions
  }, [job])

  // Business logic for job permissions
  const canEdit = job ? job.status !== 'COMPLETED' && job.status !== 'CANCELLED' : false
  
  // Due date calculations
  const dueDate = job?.due_date ? new Date(job.due_date) : null
  const releaseDate = job?.earliest_start_date ? new Date(job.earliest_start_date) : null
  const isOverdue = dueDate && dueDate < new Date() && job?.status !== 'COMPLETED'

  return {
    getAvailableTransitions,
    canEdit,
    dueDate,
    releaseDate,
    isOverdue,
  }
}

/**
 * Custom hook for job actions (edit, delete, status changes)
 * Consolidates mutation operations and callbacks
 */
export function useJobActions(job: JobInstance | undefined, onClose?: () => void) {
  const updateJobStatus = useUpdateJobStatus()
  const deleteJob = useDeleteJob()

  const handleStatusChange = useCallback(
    (newStatus: JobStatus) => {
      if (!job) return
      updateJobStatus.mutate({ id: job.instance_id, status: newStatus })
    },
    [job, updateJobStatus],
  )

  const handleDelete = useCallback(() => {
    if (!job) return
    if (
      window.confirm(
        `Are you sure you want to delete job ${job.name}? This action cannot be undone.`,
      )
    ) {
      deleteJob.mutate(job.instance_id, {
        onSuccess: () => onClose?.(),
      })
    }
  }, [job, deleteJob, onClose])

  return {
    handleStatusChange,
    handleDelete,
    updateJobStatus,
    deleteJob,
  }
}