import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/core/stores/ui-store'
import { UseCaseFactory } from '@/core/use-cases/use-case-factory'

// Type definitions for task-related operations
type TaskStatusValue = 'pending' | 'ready' | 'in_progress' | 'completed' | 'cancelled'
type SkillLevelValue = 'beginner' | 'intermediate' | 'advanced' | 'expert'

// Query keys factory for consistent caching
export const taskKeys = {
  all: ['tasks'] as const,
  lists: () => [...taskKeys.all, 'list'] as const,
  list: (filters: { status?: TaskStatusValue; jobId?: string }) =>
    [...taskKeys.lists(), filters] as const,
  details: () => [...taskKeys.all, 'detail'] as const,
  detail: (id: string) => [...taskKeys.details(), id] as const,
  byJob: (jobId: string) => [...taskKeys.all, 'job', jobId] as const,
  byStatus: (status: TaskStatusValue) => [...taskKeys.all, 'status', status] as const,
  schedulable: () => [...taskKeys.all, 'schedulable'] as const,
  active: () => [...taskKeys.all, 'active'] as const,
  setup: () => [...taskKeys.all, 'setup'] as const,
  bySkillLevel: (skillLevel: SkillLevelValue) => [...taskKeys.all, 'skill', skillLevel] as const,
  unattended: () => [...taskKeys.all, 'unattended'] as const,
  attended: () => [...taskKeys.all, 'attended'] as const,
}

/**
 * Hook to fetch tasks with optional filters
 */
export function useTasks(filters?: { status?: TaskStatusValue; jobId?: string }) {
  return useQuery({
    queryKey: taskKeys.list(filters || {}),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      
      if (filters?.jobId) {
        return await taskUseCases.getTasksByJobId(filters.jobId)
      }
      if (filters?.status) {
        return await taskUseCases.getTasksByStatus(filters.status)
      }
      // Default to paginated fetch for large datasets
      const result = await taskUseCases.getPaginatedTasks(50, 0)
      return result.tasks
    },
    staleTime: 30 * 1000, // 30 seconds - manufacturing data changes frequently
    gcTime: 5 * 60 * 1000, // 5 minutes cache
  })
}

/**
 * Hook to fetch single task by ID
 */
export function useTask(id: string) {
  return useQuery({
    queryKey: taskKeys.detail(id),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getTaskById(id)
    },
    enabled: !!id,
    staleTime: 30 * 1000,
  })
}

/**
 * Hook to fetch tasks by job ID
 */
export function useTasksByJob(jobId: string) {
  return useQuery({
    queryKey: taskKeys.byJob(jobId),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getTasksByJobId(jobId)
    },
    enabled: !!jobId,
    staleTime: 30 * 1000,
  })
}

/**
 * Hook to fetch tasks by status
 */
export function useTasksByStatus(status: TaskStatusValue) {
  return useQuery({
    queryKey: taskKeys.byStatus(status),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getTasksByStatus(status)
    },
    staleTime: 30 * 1000,
  })
}

/**
 * Hook to fetch schedulable tasks (ready status)
 */
export function useSchedulableTasks() {
  return useQuery({
    queryKey: taskKeys.schedulable(),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getSchedulableTasks()
    },
    staleTime: 15 * 1000, // Shorter cache for scheduling-critical data
    refetchInterval: 30 * 1000, // Auto-refresh for scheduling dashboard
  })
}

/**
 * Hook to fetch active tasks (in progress)
 */
export function useActiveTasks() {
  return useQuery({
    queryKey: taskKeys.active(),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getActiveTasks()
    },
    staleTime: 15 * 1000, // Shorter cache for real-time monitoring
    refetchInterval: 30 * 1000, // Auto-refresh for production dashboard
  })
}

/**
 * Hook to fetch setup tasks for priority scheduling
 */
export function useSetupTasks() {
  return useQuery({
    queryKey: taskKeys.setup(),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getSetupTasks()
    },
    staleTime: 60 * 1000, // Setup tasks change less frequently
  })
}

/**
 * Hook to fetch tasks by skill level
 */
export function useTasksBySkillLevel(skillLevel: SkillLevelValue) {
  return useQuery({
    queryKey: taskKeys.bySkillLevel(skillLevel),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getTasksBySkillLevel(skillLevel)
    },
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to fetch unattended tasks for 24/7 scheduling
 */
export function useUnattendedTasks() {
  return useQuery({
    queryKey: taskKeys.unattended(),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getUnattendedTasks()
    },
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to fetch attended tasks for business hours scheduling
 */
export function useAttendedTasks() {
  return useQuery({
    queryKey: taskKeys.attended(),
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getAttendedTasks()
    },
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to create a new task
 */
export function useCreateTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (params: {
      taskId: string
      jobId: string
      name: string
      sequence: number
      skillRequirements: Array<{
        level: SkillLevelValue
        quantity: number
      }>
      workCellRequirements: string[]
      isUnattended?: boolean
      isSetupTask?: boolean
    }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.createTask(params)
    },
    onSuccess: (task) => {
      // Add to cache and invalidate relevant queries only
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.byJob(task.jobId.toString()) })
      
      // Invalidate status-specific queries if task has initial status
      if (task.status) {
        queryClient.invalidateQueries({ queryKey: taskKeys.byStatus(task.status.value) })
      }

      addNotification({
        type: 'success',
        title: 'Task Created',
        message: `Task "${task.name.toString()}" has been created successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Create Task Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to update task status
 */
export function useUpdateTaskStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({
      taskId,
      newStatus,
      reason,
    }: {
      taskId: string
      newStatus: TaskStatusValue
      reason?: string
    }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.updateTaskStatus(taskId, newStatus, reason)
    },
    onMutate: async ({ taskId, newStatus }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: taskKeys.detail(taskId) })

      // Snapshot the previous value
      const previousTask = queryClient.getQueryData(taskKeys.detail(taskId))

      // Optimistically update the task status
      if (previousTask) {
        queryClient.setQueryData(taskKeys.detail(taskId), {
          ...previousTask,
          status: { value: newStatus },
          updated_at: new Date().toISOString(),
        })
      }

      return { previousTask, taskId }
    },
    onSuccess: (task, { newStatus }) => {
      // Update specific task in cache
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)

      // Only invalidate queries affected by the status change
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.byJob(task.jobId.toString()) })
      queryClient.invalidateQueries({ queryKey: taskKeys.byStatus(newStatus) })
      
      // Invalidate previous status queries if status changed
      if (task.status.value !== newStatus) {
        queryClient.invalidateQueries({ queryKey: taskKeys.byStatus(task.status.value) })
      }
      
      // Invalidate specialized queries based on new status
      if (newStatus === 'ready') {
        queryClient.invalidateQueries({ queryKey: taskKeys.schedulable() })
      }
      if (newStatus === 'in_progress') {
        queryClient.invalidateQueries({ queryKey: taskKeys.active() })
      }

      addNotification({
        type: 'success',
        title: 'Task Status Updated',
        message: `Task status changed to ${task.status.toString()}`,
      })
    },
    onError: (error, { taskId }, context) => {
      // Rollback optimistic update
      if (context?.previousTask) {
        queryClient.setQueryData(taskKeys.detail(taskId), context.previousTask)
      }

      addNotification({
        type: 'error',
        title: 'Status Update Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to mark task as ready
 */
export function useMarkTaskReady() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (taskId: string) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.markTaskReady(taskId)
    },
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.schedulable() })

      addNotification({
        type: 'success',
        title: 'Task Ready',
        message: `Task "${task.name.toString()}" is now ready for scheduling`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Mark Ready Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to schedule task
 */
export function useScheduleTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({ taskId, scheduledAt }: { taskId: string; scheduledAt: Date }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.scheduleTask(taskId, scheduledAt)
    },
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.schedulable() })

      addNotification({
        type: 'success',
        title: 'Task Scheduled',
        message: `Task "${task.name.toString()}" has been scheduled`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Scheduling Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to start task execution
 */
export function useStartTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({ taskId, startedAt }: { taskId: string; startedAt?: Date }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.startTask(taskId, startedAt)
    },
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.active() })

      addNotification({
        type: 'info',
        title: 'Task Started',
        message: `Task "${task.name.toString()}" execution has started`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Start Task Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to complete task
 */
export function useCompleteTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({ taskId, completedAt }: { taskId: string; completedAt?: Date }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.completeTask(taskId, completedAt)
    },
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
      queryClient.invalidateQueries({ queryKey: taskKeys.active() })

      addNotification({
        type: 'success',
        title: 'Task Completed',
        message: `Task "${task.name.toString()}" has been completed successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Complete Task Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to cancel task
 */
export function useCancelTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({ taskId, reason }: { taskId: string; reason: string }) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.cancelTask(taskId, reason)
    },
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id.toString()), task)
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })

      addNotification({
        type: 'warning',
        title: 'Task Cancelled',
        message: `Task "${task.name.toString()}" has been cancelled`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Cancel Task Failed',
        message: error.message,
      })
    },
  })
}

/**
 * Hook to validate task precedence
 */
export function useValidateTaskPrecedence(jobId: string) {
  return useQuery({
    queryKey: ['tasks', 'precedence', jobId],
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.validateTaskPrecedence(jobId)
    },
    enabled: !!jobId,
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to get task count for analytics
 */
export function useTaskCount() {
  return useQuery({
    queryKey: ['tasks', 'count'],
    queryFn: async () => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.getTaskCount()
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - analytics data can be less fresh
  })
}

/**
 * Hook to delete task
 */
export function useDeleteTask() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (taskId: string) => {
      const factory = UseCaseFactory.getInstance()
      const taskUseCases = await factory.getTaskUseCases()
      return await taskUseCases.deleteTask(taskId)
    },
    onSuccess: (_, taskId) => {
      // Get task data before removing to optimize invalidations
      const deletedTask = queryClient.getQueryData(taskKeys.detail(taskId))
      
      // Remove from cache
      queryClient.removeQueries({ queryKey: taskKeys.detail(taskId) })
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() })

      // Only invalidate specific queries if we have task data
      if (deletedTask && typeof deletedTask === 'object' && 'jobId' in deletedTask) {
        queryClient.invalidateQueries({ queryKey: taskKeys.byJob(String(deletedTask.jobId)) })
        
        if ('status' in deletedTask && typeof deletedTask.status === 'object' && deletedTask.status && 'value' in deletedTask.status) {
          queryClient.invalidateQueries({ queryKey: taskKeys.byStatus(String(deletedTask.status.value)) })
          
          // Invalidate specialized queries based on status
          if (deletedTask.status.value === 'ready') {
            queryClient.invalidateQueries({ queryKey: taskKeys.schedulable() })
          }
          if (deletedTask.status.value === 'in_progress') {
            queryClient.invalidateQueries({ queryKey: taskKeys.active() })
          }
        }
      }

      addNotification({
        type: 'success',
        title: 'Task Deleted',
        message: 'Task has been deleted successfully',
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Task Failed',
        message: error.message,
      })
    },
  })
}
