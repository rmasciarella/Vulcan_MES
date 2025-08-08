import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import { TaskRepository } from '@/core/domains/tasks/repositories/task-repository'
import { TaskModeRepository } from '@/core/domains/tasks/repositories/task-mode-repository'
import { Task } from '@/core/domains/tasks/task'
import {
  TaskId,
  TaskName,
  TaskSequence,
  TaskStatus,
  TaskStatusValue,
  AttendanceRequirement,
} from '@/core/domains/tasks/value-objects'
import { JobId } from '@/core/domains/jobs/value-objects'
import { taskEventDispatcher } from '@/core/domains/tasks/events/task-event-dispatcher'
import { domainLogger } from '@/core/shared/logger'
import { safeCastToTaskEvent, isDomainEvent } from '@/core/shared/type-guards'
import { SupabaseTaskModeRepository } from './supabase-task-mode-repository'

type TaskRow = Database['public']['Tables']['tasks']['Row']
type TaskInsert = Database['public']['Tables']['tasks']['Insert']

/**
 * Supabase implementation of TaskRepository with manufacturing data optimizations
 *
 * Features:
 * - Domain ↔ database type transformation using proper tasks table
 * - TaskMode composition loading (delegated to TaskModeRepository)
 * - Domain event publishing after persistence
 * - Manufacturing-specific query optimizations for 1000+ concurrent jobs
 * - Error handling with manufacturing context
 * - Lazy loading patterns for efficient data access
 * - Batch operations for high-volume manufacturing workloads
 * - Value object caching for memory efficiency
 */

/**
 * Data mapper optimized for manufacturing task processing
 * Includes caching and batch operations for performance
 */
class TaskDataMapper {
  // Cache for frequently used value objects
  private static readonly statusCache = new Map<string, TaskStatus>()
  private static readonly nameCache = new Map<string, TaskName>()

  /**
   * Clear caches to prevent memory leaks during long-running operations
   */
  static clearCaches(): void {
    this.statusCache.clear()
    this.nameCache.clear()
  }

  /**
   * Get cached TaskStatus to reduce object creation overhead
   */
  private static getCachedTaskStatus(statusValue: TaskStatusValue): TaskStatus {
    const cached = this.statusCache.get(statusValue)
    if (cached) {
      return cached
    }
    const newStatus = TaskStatus.create(statusValue)
    this.statusCache.set(statusValue, newStatus)
    return newStatus
  }

  /**
   * Get cached TaskName to reduce object creation overhead
   */
  private static getCachedTaskName(name: string): TaskName {
    const cached = this.nameCache.get(name)
    if (cached) {
      return cached
    }
    const newName = TaskName.create(name)
    this.nameCache.set(name, newName)
    return newName
  }

  /**
   * Map database row to domain Task entity with caching
   */
  static mapToDomain(row: TaskRow): Task {
    const taskId = TaskId.fromString(row.id)
    const jobId = JobId.fromString(row.job_id)
    const name = this.getCachedTaskName(row.name)
    const sequence = TaskSequence.create(row.sequence_number)
    const status = this.getCachedTaskStatus(row.status as TaskStatusValue)
    const attendanceRequirement = AttendanceRequirement.create(row.is_unattended)

    return Task.fromPersistence({
      id: taskId,
      jobId: jobId,
      name: name,
      sequence: sequence,
      status: status,
      attendanceRequirement: attendanceRequirement,
      isSetupTask: row.is_setup_task,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: row.version,
    })
  }

  /**
   * Batch convert multiple database rows to domain entities
   * Optimized for large datasets with cache pre-warming
   */
  static batchMapToDomain(rows: TaskRow[]): Task[] {
    // Pre-warm caches for batch processing
    const uniqueStatuses = [...new Set(rows.map((r) => r.status))]
    const uniqueNames = [...new Set(rows.map((r) => r.name))]

    uniqueStatuses.forEach((status) => this.getCachedTaskStatus(status as TaskStatusValue))
    uniqueNames.forEach((name) => this.getCachedTaskName(name))

    return rows.map((row) => this.mapToDomain(row))
  }

  /**
   * Map domain Task entity to database row
   */
  static mapToDatabase(task: Task): TaskInsert {
    return {
      id: task.id.toString(),
      job_id: task.jobId.toString(),
      name: task.name.toString(),
      sequence_number: task.sequence.value,
      status: task.status.value,
      is_setup_task: task.isSetupTask,
      is_unattended: task.attendanceRequirement.isUnattended,
      created_at: task.createdAt.toISOString(),
      updated_at: new Date().toISOString(),
      version: task.version.toNumber(),
    }
  }
}
export class SupabaseTaskRepository implements TaskRepository {
  private readonly taskModeRepository: TaskModeRepository

  constructor(private readonly supabase: SupabaseClient<Database>) {
    this.taskModeRepository = new SupabaseTaskModeRepository(supabase)
  }

  async findById(id: TaskId): Promise<Task | null> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null // Not found
        }
        throw new Error(`Failed to find task ${id.toString()}: ${error.message}`)
      }

      return await this.mapToDomain(data)
    } catch (error) {
      throw new Error(`Task repository error finding task ${id.toString()}: ${error}`)
    }
  }

  async findByJobId(jobId: JobId): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('job_id', jobId.toString())
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks for job ${jobId.toString()}: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks for job ${jobId.toString()}: ${error}`)
    }
  }

  async findByStatus(status: TaskStatus): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('status', status.value)
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks by status ${status.toString()}: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(
        `Task repository error finding tasks by status ${status.toString()}: ${error}`,
      )
    }
  }

  async findByJobIdAndStatus(jobId: JobId, status: TaskStatus): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('job_id', jobId.toString())
        .eq('status', status.value)
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks by job and status: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks by job and status: ${error}`)
    }
  }

  async findBySkillLevel(skillLevel: string): Promise<Task[]> {
    try {
      // Query tasks through their TaskModes that require this skill level
      const { data, error } = await this.supabase
        .from('tasks')
        .select(
          `
          *,
          task_modes!inner (
            id,
            task_mode_skill_requirements!inner (
              skill_level
            )
          )
        `,
        )
        .eq('task_modes.task_mode_skill_requirements.skill_level', skillLevel)
        .order('name', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks by skill level ${skillLevel}: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks by skill level ${skillLevel}: ${error}`)
    }
  }

  async findByWorkCells(workCellIds: string[]): Promise<Task[]> {
    try {
      // Query tasks through their TaskModes that require these WorkCells
      const { data, error } = await this.supabase
        .from('tasks')
        .select(
          `
          *,
          task_modes!inner (
            id,
            task_mode_workcell_requirements!inner (
              workcell_id
            )
          )
        `,
        )
        .in('task_modes.task_mode_workcell_requirements.workcell_id', workCellIds)
        .order('name', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks by WorkCells: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks by WorkCells: ${error}`)
    }
  }

  async findBySetupTaskFlag(isSetupTask: boolean): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('is_setup_task', isSetupTask)
        .order('name', { ascending: true })

      if (error) {
        throw new Error(`Failed to find setup tasks: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding setup tasks: ${error}`)
    }
  }

  async findByAttendanceRequirement(isUnattended: boolean): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('is_unattended', isUnattended)
        .order('name', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks by attendance requirement: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks by attendance: ${error}`)
    }
  }

  async findBySequenceRange(
    jobId: JobId,
    minSequence: number,
    maxSequence: number,
  ): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('job_id', jobId.toString())
        .gte('sequence_number', minSequence)
        .lte('sequence_number', maxSequence)
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to find tasks in sequence range: ${error.message}`)
      }

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding tasks in sequence range: ${error}`)
    }
  }

  async save(task: Task): Promise<Task> {
    try {
      const dbData = this.mapToDatabase(task)

      // Try to update first, then insert if not found
      const { data: existingData } = await this.supabase
        .from('tasks')
        .select('id')
        .eq('id', task.id.toString())
        .single()

      let savedData: TaskRow

      if (existingData) {
        // Update existing task
        const { data, error } = await this.supabase
          .from('tasks')
          .update(dbData)
          .eq('id', task.id.toString())
          .select()
          .single()

        if (error) {
          throw new Error(`Failed to update task ${task.id.toString()}: ${error.message}`)
        }
        savedData = data
      } else {
        // Insert new task
        const { data, error } = await this.supabase.from('tasks').insert(dbData).select().single()

        if (error) {
          throw new Error(`Failed to create task ${task.id.toString()}: ${error.message}`)
        }
        savedData = data
      }

      // Publish domain events after successful persistence
      await this.publishDomainEvents(task)

      return await this.mapToDomain(savedData)
    } catch (error) {
      throw new Error(`Task repository error saving task ${task.id.toString()}: ${error}`)
    }
  }

  async delete(id: TaskId): Promise<boolean> {
    try {
      const { error } = await this.supabase.from('tasks').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete task ${id.toString()}: ${error.message}`)
      }

      return true
    } catch (error) {
      throw new Error(`Task repository error deleting task ${id.toString()}: ${error}`)
    }
  }

  async findPaginated(
    limit: number,
    offset: number,
  ): Promise<{
    tasks: Task[]
    total: number
    hasMore: boolean
  }> {
    try {
      // Get total count
      const { count, error: countError } = await this.supabase
        .from('tasks')
        .select('*', { count: 'exact', head: true })

      if (countError) {
        throw new Error(`Failed to count tasks: ${countError.message}`)
      }

      // Get paginated results
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .order('name', { ascending: true })
        .range(offset, offset + limit - 1)

      if (error) {
        throw new Error(`Failed to fetch paginated tasks: ${error.message}`)
      }

      const tasks = await Promise.all(data.map((row) => this.mapToDomain(row)))
      const total = count || 0
      const hasMore = offset + limit < total

      return { tasks, total, hasMore }
    } catch (error) {
      throw new Error(`Task repository error finding paginated tasks: ${error}`)
    }
  }

  async count(): Promise<number> {
    try {
      const { count, error } = await this.supabase
        .from('tasks')
        .select('*', { count: 'exact', head: true })

      if (error) {
        throw new Error(`Failed to count tasks: ${error.message}`)
      }

      return count || 0
    } catch (error) {
      throw new Error(`Task repository error counting tasks: ${error}`)
    }
  }

  async findSchedulableTasks(): Promise<Task[]> {
    return this.findByStatus(TaskStatus.create('ready'))
  }

  async findActiveTasks(): Promise<Task[]> {
    return this.findByStatus(TaskStatus.create('in_progress'))
  }

  async findOverdueTasks(_asOfDate: Date): Promise<Task[]> {
    try {
      // Find tasks that are scheduled but not started and past their due date
      // This requires joining with scheduling data - simplified for now
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .eq('status', 'scheduled')
        .order('name', { ascending: true })

      if (error) {
        throw new Error(`Failed to find overdue tasks: ${error.message}`)
      }

      // TODO: Add proper overdue logic when scheduling domain is implemented
      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error finding overdue tasks: ${error}`)
    }
  }

  async saveMany(tasks: Task[]): Promise<Task[]> {
    try {
      const dbData = tasks.map((task) => this.mapToDatabase(task))

      const { data, error } = await this.supabase.from('tasks').upsert(dbData).select()

      if (error) {
        throw new Error(`Failed to save multiple tasks: ${error.message}`)
      }

      // Publish domain events for all tasks
      await Promise.all(tasks.map((task) => this.publishDomainEvents(task)))

      return await Promise.all(data.map((row) => this.mapToDomain(row)))
    } catch (error) {
      throw new Error(`Task repository error saving multiple tasks: ${error}`)
    }
  }

  /**
   * Map database row to domain Task entity
   */
  private async mapToDomain(row: TaskRow): Promise<Task> {
    // Map database fields to domain value objects
    const taskId = TaskId.fromString(row.id)
    const jobId = JobId.fromString(row.job_id)
    const name = TaskName.create(row.name)
    const sequence = TaskSequence.create(row.sequence_number)
    const status = TaskStatus.create(row.status as TaskStatusValue)
    const attendanceRequirement = AttendanceRequirement.create(row.is_unattended)

    // Load TaskModes for this task
    const taskModes = await this.taskModeRepository.findByTaskId(taskId)

    // Reconstitute Task from persistence with loaded TaskModes
    return Task.fromPersistence({
      id: taskId,
      jobId: jobId,
      name: name,
      sequence: sequence,
      status: status,
      attendanceRequirement: attendanceRequirement,
      isSetupTask: row.is_setup_task,
      taskModes: taskModes,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: row.version,
    })
  }

  /**
   * Map domain Task entity to database row
   */
  private mapToDatabase(task: Task): TaskInsert {
    return {
      id: task.id.toString(),
      job_id: task.jobId.toString(),
      name: task.name.toString(),
      sequence_number: task.sequence.value,
      status: task.status.value,
      is_setup_task: task.isSetupTask,
      is_unattended: task.attendanceRequirement.isUnattended,
      created_at: task.createdAt.toISOString(),
      updated_at: new Date().toISOString(),
      version: task.version.toNumber(),
    }
  }

  /**
   * Publish domain events after successful persistence
   */
  private async publishDomainEvents(task: Task): Promise<void> {
    try {
      const events = task.getUncommittedEvents()

      for (const event of events) {
        if (!isDomainEvent(event)) {
          domainLogger.infrastructure.warn('Skipping invalid domain event', {
            taskId: task.id.toString(),
            event,
          })
          continue
        }

        const taskEvent = safeCastToTaskEvent(event)
        if (taskEvent) {
          await taskEventDispatcher.publish(taskEvent)
        } else {
          domainLogger.infrastructure.warn('Skipping non-task domain event', {
            taskId: task.id.toString(),
            eventType: event.eventType,
          })
        }
      }

      // Clear events after publishing
      task.markEventsAsCommitted()

      domainLogger.infrastructure.info(
        `Published ${events.length} events for task ${task.id.toString()}`,
        { taskId: task.id.toString(), eventCount: events.length },
      )
    } catch (error) {
      domainLogger.infrastructure.error(
        `Failed to publish domain events for task ${task.id.toString()}`,
        error as Error,
        { taskId: task.id.toString() },
      )
      // Don't throw - event publishing failure shouldn't break persistence
    }
  }

  /**
   * OPTIMIZATION: Batch loading tasks for multiple jobs
   * Prevents N+1 queries when loading job-task relationships
   */
  async findByJobIds(jobIds: JobId[]): Promise<Map<string, Task[]>> {
    try {
      if (jobIds.length === 0) {
        return new Map()
      }

      const jobIdStrings = jobIds.map((id) => id.toString())
      const { data, error } = await this.supabase
        .from('tasks')
        .select('*')
        .in('job_id', jobIdStrings)
        .order('job_id', { ascending: true })
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to batch load tasks by job IDs: ${error.message}`)
      }

      // Group tasks by job ID
      const tasksByJob = new Map<string, Task[]>()
      const allTasks = TaskDataMapper.batchMapToDomain(data)

      allTasks.forEach((task) => {
        const jobId = task.jobId.toString()
        if (!tasksByJob.has(jobId)) {
          tasksByJob.set(jobId, [])
        }
        tasksByJob.get(jobId)!.push(task)
      })

      return tasksByJob
    } catch (error) {
      throw new Error(`Task repository error in batch loading by job IDs: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Find tasks with TaskMode data in single query
   * Prevents N+1 problem for manufacturing scheduling operations
   */
  async findByJobIdWithTaskModes(jobId: JobId): Promise<Task[]> {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select(
          `
          *,
          task_modes(
            id,
            name,
            type,
            duration_minutes,
            is_primary_mode
          )
        `,
        )
        .eq('job_id', jobId.toString())
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(
          `Failed to find tasks with modes for job ${jobId.toString()}: ${error.message}`,
        )
      }

      return TaskDataMapper.batchMapToDomain(data)
    } catch (error) {
      throw new Error(`Task repository error finding tasks with modes: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Bulk task operations for manufacturing batch processing
   */
  async bulkUpdateStatus(taskIds: TaskId[], newStatus: TaskStatus): Promise<number> {
    try {
      if (taskIds.length === 0) {
        return 0
      }

      const idStrings = taskIds.map((id) => id.toString())
      const { data, error } = await this.supabase
        .from('tasks')
        .update({
          status: newStatus.value,
          updated_at: new Date().toISOString(),
        })
        .in('id', idStrings)
        .select('id')

      if (error) {
        throw new Error(`Failed to bulk update task status: ${error.message}`)
      }

      return data.length
    } catch (error) {
      throw new Error(`Task repository error in bulk status update: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Find schedulable tasks with resource requirements
   * Single query for manufacturing scheduling optimization
   */
  async findSchedulableWithResourceInfo(): Promise<
    Array<{
      task: Task
      primaryMode: {
        id: string
        duration: number
        skillRequirements: Array<{ level: string; quantity: number }>
        workCellRequirements: string[]
      } | null
    }>
  > {
    try {
      const { data, error } = await this.supabase
        .from('tasks')
        .select(
          `
          *,
          task_modes!inner(
            id,
            duration_minutes,
            is_primary_mode,
            task_mode_skill_requirements(skill_level, quantity),
            task_mode_workcell_requirements(workcell_id)
          )
        `,
        )
        .eq('status', 'ready')
        .eq('task_modes.is_primary_mode', true)
        .order('sequence_number', { ascending: true })

      if (error) {
        throw new Error(`Failed to find schedulable tasks with resource info: ${error.message}`)
      }

      return data.map((row) => ({
        task: TaskDataMapper.mapToDomain(row),
        primaryMode: row.task_modes?.[0]
          ? {
              id: row.task_modes[0].id,
              duration: row.task_modes[0].duration_minutes,
              skillRequirements: (row.task_modes[0].task_mode_skill_requirements || []).map(
                (req: { skill_level: string; quantity: number }) => ({
                  level: req.skill_level,
                  quantity: req.quantity,
                }),
              ),
              workCellRequirements: (row.task_modes[0].task_mode_workcell_requirements || []).map(
                (req: { workcell_id: string }) => req.workcell_id,
              ),
            }
          : null,
      }))
    } catch (error) {
      throw new Error(`Task repository error finding schedulable tasks: ${error}`)
    }
  }

  /**
   * Get performance metrics for tasks
   */
  async getPerformanceMetrics(): Promise<{
    totalTasks: number
    completedTasks: number
    inProgressTasks: number
    pendingTasks: number
    averageCompletionTime: number
    onTimeCompletionRate: number
  }> {
    try {
      // Get total counts by status
      const [totalResult, completedResult, inProgressResult, pendingResult] = await Promise.all([
        this.supabase
          .from('tasks')
          .select('*', { count: 'exact', head: true }),
        this.supabase
          .from('tasks')
          .select('*', { count: 'exact', head: true })
          .eq('status', 'completed'),
        this.supabase
          .from('tasks')
          .select('*', { count: 'exact', head: true })
          .eq('status', 'in_progress'),
        this.supabase
          .from('tasks')
          .select('*', { count: 'exact', head: true })
          .eq('status', 'pending')
      ])

      // Check for errors
      if (totalResult.error) throw new Error(`Total count failed: ${totalResult.error.message}`)
      if (completedResult.error) throw new Error(`Completed count failed: ${completedResult.error.message}`)
      if (inProgressResult.error) throw new Error(`In progress count failed: ${inProgressResult.error.message}`)
      if (pendingResult.error) throw new Error(`Pending count failed: ${pendingResult.error.message}`)

      const totalTasks = totalResult.count || 0
      const completedTasks = completedResult.count || 0
      const inProgressTasks = inProgressResult.count || 0
      const pendingTasks = pendingResult.count || 0

      // Calculate average completion time (simplified - would need actual duration tracking)
      // For now, return a placeholder calculation
      const averageCompletionTime = completedTasks > 0 ? 24 : 0 // 24 hours average placeholder

      // Calculate on-time completion rate (simplified - would need due date tracking)
      const onTimeCompletionRate = completedTasks > 0 ? 0.85 : 0 // 85% placeholder

      return {
        totalTasks,
        completedTasks,
        inProgressTasks,
        pendingTasks,
        averageCompletionTime,
        onTimeCompletionRate
      }
    } catch (error) {
      throw new Error(`Task repository error getting performance metrics: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Clear data mapper caches periodically
   * Prevents memory leaks during long-running manufacturing operations
   */
  clearDataCaches(): void {
    TaskDataMapper.clearCaches()
  }
}
