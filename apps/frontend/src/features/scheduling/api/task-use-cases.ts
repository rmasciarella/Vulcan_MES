import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import type { Task, TaskInsert, TaskUpdate } from '@/core/types/database'

type TaskStatus = 'pending' | 'ready' | 'in_progress' | 'completed' | 'cancelled' | 'blocked' | 'on_hold' | 'scheduled'
type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert'

/**
 * Filters interface for task queries
 */
export interface TaskListFilters {
  status?: TaskStatus | TaskStatus[]
  jobId?: string
  machineId?: string
  operatorId?: string
  search?: string
  sortBy?: 'task_name' | 'status' | 'scheduled_start' | 'scheduled_end' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

/**
 * Task creation data structure
 */
export interface CreateTaskData {
  taskId: string
  jobId: string
  name: string
  sequence: number
  skillRequirements: Array<{
    level: SkillLevel
    quantity: number
  }>
  workCellRequirements: string[]
  isUnattended?: boolean
  isSetupTask?: boolean
  machineId?: string
  operatorId?: string
  scheduledStart?: string
  scheduledEnd?: string
  status?: TaskStatus
}

/**
 * Task update data structure  
 */
export interface UpdateTaskData {
  task_name?: string
  status?: TaskStatus
  machine_id?: string
  operator_id?: string
  scheduled_start?: string
  scheduled_end?: string
}

/**
 * Task statistics data structure
 */
export interface TaskStats {
  total: number
  [key: string]: number  // Allow for dynamic status counts
}

/**
 * Paginated tasks response
 */
export interface PaginatedTasksResponse {
  tasks: Task[]
  hasMore: boolean
  total: number
  page: number
  pageSize: number
}

/**
 * Business logic layer for task operations
 * Encapsulates all task-related use cases and domain logic
 */
export class TaskUseCases {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Fetch tasks with optional filtering and pagination
   */
  async getTasks(filters?: TaskListFilters): Promise<Task[]> {
    let query = this.supabase
      .from('scheduled_tasks')
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

    // Apply jobId filter
    if (filters?.jobId) {
      // Note: scheduled_tasks doesn't have job_id directly, may need to join or use a different approach
      // For now, we'll skip this filter since it's not in the current schema
    }

    // Apply machineId filter
    if (filters?.machineId) {
      query = query.eq('machine_id', filters.machineId)
    }

    // Apply operatorId filter
    if (filters?.operatorId) {
      query = query.eq('operator_id', filters.operatorId)
    }

    // Apply search filter on task name
    if (filters?.search) {
      query = query.ilike('task_name', `%${filters.search}%`)
    }

    // Apply sorting
    if (filters?.sortBy && filters?.sortOrder) {
      const ascending = filters.sortOrder === 'asc'
      switch (filters.sortBy) {
        case 'task_name':
          query = query.order('task_name', { ascending })
          break
        case 'status':
          query = query.order('status', { ascending })
          break
        case 'scheduled_start':
          query = query.order('scheduled_start', { ascending })
          break
        case 'scheduled_end':
          query = query.order('scheduled_end', { ascending })
          break
        case 'created_at':
          query = query.order('created_at', { ascending })
          break
        default:
          // Default sorting by created_at desc
          break
      }
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch tasks: ${error.message}`)
    }

    return data as Task[]
  }

  /**
   * Fetch a single task by ID
   */
  async getTask(id: string): Promise<Task> {
    const { data, error } = await this.supabase
      .from('scheduled_tasks')
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        throw new Error(`Task with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch task: ${error.message}`)
    }

    return data as Task
  }

  /**
   * Alias for getTask for consistency
   */
  async getTaskById(id: string): Promise<Task> {
    return this.getTask(id)
  }

  /**
   * Get tasks by job ID (placeholder implementation since job_id is not in scheduled_tasks)
   */
  async getTasksByJobId(jobId: string): Promise<Task[]> {
    // Since scheduled_tasks doesn't have job_id, this is a placeholder
    // In a real implementation, you might need to join with another table
    console.warn('getTasksByJobId: job_id not available in scheduled_tasks, returning all tasks')
    return this.getTasks()
  }

  /**
   * Get tasks by status
   */
  async getTasksByStatus(status: string): Promise<Task[]> {
    return this.getTasks({ status: status as TaskStatus })
  }

  /**
   * Get schedulable tasks (ready status)
   */
  async getSchedulableTasks(): Promise<Task[]> {
    return this.getTasks({ status: 'ready' })
  }

  /**
   * Get active tasks (in progress)
   */
  async getActiveTasks(): Promise<Task[]> {
    return this.getTasks({ status: 'in_progress' })
  }

  /**
   * Get setup tasks (placeholder - would need additional metadata)
   */
  async getSetupTasks(): Promise<Task[]> {
    // Since there's no setup flag in the schema, return tasks with setup-like names
    return this.getTasks({ search: 'setup' })
  }

  /**
   * Get tasks by skill level (placeholder - would need skill metadata)
   */
  async getTasksBySkillLevel(skillLevel: string): Promise<Task[]> {
    console.warn('getTasksBySkillLevel: skill level metadata not available in scheduled_tasks')
    return this.getTasks()
  }

  /**
   * Get unattended tasks (placeholder - would need metadata)
   */
  async getUnattendedTasks(): Promise<Task[]> {
    console.warn('getUnattendedTasks: unattended flag not available in scheduled_tasks')
    return this.getTasks()
  }

  /**
   * Get attended tasks (placeholder - would need metadata)
   */
  async getAttendedTasks(): Promise<Task[]> {
    console.warn('getAttendedTasks: attended flag not available in scheduled_tasks')
    return this.getTasks()
  }

  /**
   * Fetch tasks with pagination support
   */
  async getPaginatedTasks(
    pageSize: number = 50, 
    offset: number = 0, 
    filters?: TaskListFilters
  ): Promise<PaginatedTasksResponse> {
    // Get total count for pagination metadata
    let countQuery = this.supabase
      .from('scheduled_tasks')
      .select('*', { count: 'exact', head: true })

    // Apply same filters for count
    if (filters?.status) {
      if (Array.isArray(filters.status)) {
        countQuery = countQuery.in('status', filters.status)
      } else {
        countQuery = countQuery.eq('status', filters.status)
      }
    }
    if (filters?.machineId) {
      countQuery = countQuery.eq('machine_id', filters.machineId)
    }
    if (filters?.operatorId) {
      countQuery = countQuery.eq('operator_id', filters.operatorId)
    }
    if (filters?.search) {
      countQuery = countQuery.ilike('task_name', `%${filters.search}%`)
    }

    const { count, error: countError } = await countQuery

    if (countError) {
      throw new Error(`Failed to count tasks: ${countError.message}`)
    }

    // Get paginated data
    const tasks = await this.getTasks(filters)
    const paginatedTasks = tasks.slice(offset, offset + pageSize)

    return {
      tasks: paginatedTasks,
      hasMore: offset + pageSize < tasks.length,
      total: count || 0,
      page: Math.floor(offset / pageSize),
      pageSize,
    }
  }

  /**
   * Get task count statistics for analytics/dashboard
   */
  async getTaskCount(): Promise<TaskStats> {
    const { data: tasks, error } = await this.supabase
      .from('scheduled_tasks')
      .select('status')

    if (error) {
      throw new Error(`Failed to get task counts: ${error.message}`)
    }

    const statusCounts = (tasks || []).reduce((acc, task) => {
      const status = task.status || 'pending'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    return {
      total: tasks?.length || 0,
      ...statusCounts,
    }
  }

  /**
   * Validate task precedence (placeholder implementation)
   */
  async validateTaskPrecedence(jobId: string): Promise<boolean> {
    console.warn('validateTaskPrecedence: precedence validation not implemented')
    return true
  }

  /**
   * Create a new task
   */
  async createTask(taskData: CreateTaskData): Promise<Task> {
    const insertData: TaskInsert = {
      task_name: taskData.name,
      status: taskData.status || 'pending',
      machine_id: taskData.machineId,
      operator_id: taskData.operatorId,
      scheduled_start: taskData.scheduledStart || new Date().toISOString(),
      scheduled_end: taskData.scheduledEnd || new Date(Date.now() + 3600000).toISOString(), // 1 hour later
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    const { data, error } = await this.supabase
      .from('scheduled_tasks')
      .insert(insertData)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to create task: ${error.message}`)
    }

    return data as Task
  }

  /**
   * Update an existing task
   */
  async updateTask(id: string, updateData: UpdateTaskData): Promise<Task> {
    const updates: TaskUpdate = {
      updated_at: new Date().toISOString(),
      ...updateData,
    }

    const { data, error } = await this.supabase
      .from('scheduled_tasks')
      .update(updates)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update task: ${error.message}`)
    }

    return data as Task
  }

  /**
   * Update task status
   */
  async updateTaskStatus(id: string, status: string, reason?: string): Promise<Task> {
    return this.updateTask(id, { status: status as TaskStatus })
  }

  /**
   * Delete a task
   */
  async deleteTask(id: string): Promise<void> {
    const { error } = await this.supabase
      .from('scheduled_tasks')
      .delete()
      .eq('id', id)

    if (error) {
      throw new Error(`Failed to delete task: ${error.message}`)
    }
  }

  /**
   * Mark task as ready
   */
  async markTaskReady(id: string): Promise<Task> {
    return this.updateTaskStatus(id, 'ready')
  }

  /**
   * Schedule task
   */
  async scheduleTask(id: string, scheduledAt: Date): Promise<Task> {
    return this.updateTask(id, {
      scheduled_start: scheduledAt.toISOString(),
      status: 'scheduled',
    })
  }

  /**
   * Start task execution
   */
  async startTask(id: string, startedAt?: Date): Promise<Task> {
    return this.updateTask(id, {
      scheduled_start: (startedAt || new Date()).toISOString(),
      status: 'in_progress',
    })
  }

  /**
   * Complete task
   */
  async completeTask(id: string, completedAt?: Date): Promise<Task> {
    return this.updateTask(id, {
      scheduled_end: (completedAt || new Date()).toISOString(),
      status: 'completed',
    })
  }

  /**
   * Cancel task
   */
  async cancelTask(id: string, reason: string): Promise<Task> {
    return this.updateTaskStatus(id, 'cancelled', reason)
  }
}