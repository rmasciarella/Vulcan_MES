import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import { TaskModeRepository } from '@/core/domains/tasks/repositories/task-mode-repository'
import { TaskMode } from '@/core/domains/tasks/entities/TaskMode'
import {
  TaskModeId,
  TaskModeName,
  TaskModeDuration,
  TaskModeType,
  TaskModeTypeValue,
} from '@/core/domains/tasks/value-objects/task-mode-value-objects'
import { TaskId, SkillLevel, WorkCellId } from '@/core/domains/tasks/value-objects'

type TaskModeInsert = Database['public']['Tables']['task_modes']['Insert']
type SkillRequirementRow = Database['public']['Tables']['task_mode_skill_requirements']['Row']
type WorkCellRequirementRow = Database['public']['Tables']['task_mode_workcell_requirements']['Row']

/**
 * Supabase implementation of TaskModeRepository
 *
 * Handles the complex composition of TaskMode entities with their:
 * - Skill requirements (separate table)
 * - WorkCell requirements (separate table)
 * - Full domain validation and type safety
 */
export class SupabaseTaskModeRepository implements TaskModeRepository {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  async findById(id: TaskModeId): Promise<TaskMode | null> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null // Not found
        }
        throw new Error(`Failed to find task mode ${id.toString()}: ${error.message}`)
      }

      return this.mapToDomain(data)
    } catch (error) {
      throw new Error(`TaskMode repository error finding task mode ${id.toString()}: ${error}`)
    }
  }

  async findByTaskId(taskId: TaskId): Promise<TaskMode[]> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .eq('task_id', taskId.toString())
        .order('is_primary_mode', { ascending: false }) // Primary mode first

      if (error) {
        throw new Error(`Failed to find task modes for task ${taskId.toString()}: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(
        `TaskMode repository error finding modes for task ${taskId.toString()}: ${error}`,
      )
    }
  }

  async findPrimaryByTaskId(taskId: TaskId): Promise<TaskMode | null> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .eq('task_id', taskId.toString())
        .eq('is_primary_mode', true)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null // Not found
        }
        throw new Error(
          `Failed to find primary task mode for task ${taskId.toString()}: ${error.message}`,
        )
      }

      return this.mapToDomain(data)
    } catch (error) {
      throw new Error(
        `TaskMode repository error finding primary mode for task ${taskId.toString()}: ${error}`,
      )
    }
  }

  async findByType(type: TaskModeType): Promise<TaskMode[]> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .eq('type', type.value)

      if (error) {
        throw new Error(`Failed to find task modes by type ${type.value}: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding modes by type ${type.value}: ${error}`)
    }
  }

  async findExecutableWithSkills(
    availableSkills: Array<{ level: string; count: number }>,
  ): Promise<TaskMode[]> {
    try {
      // This is a complex query - we need to find TaskModes where ALL required skills are satisfied
      // For now, we'll fetch all modes and filter in memory
      const { data, error } = await this.supabase.from('task_modes').select(`
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `)

      if (error) {
        throw new Error(`Failed to find executable task modes: ${error.message}`)
      }

      const taskModes = data.map((row) => this.mapToDomain(row))

      // Filter modes that can be executed with available skills
      return taskModes.filter((mode) => mode.canBeExecutedByOperators(availableSkills))
    } catch (error) {
      throw new Error(`TaskMode repository error finding executable modes: ${error}`)
    }
  }

  async findCompatibleWithWorkCells(workCellIds: string[]): Promise<TaskMode[]> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements!inner(*)
        `,
        )
        .in('task_mode_workcell_requirements.workcell_id', workCellIds)

      if (error) {
        throw new Error(`Failed to find compatible task modes: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding compatible modes: ${error}`)
    }
  }

  async findOptimalMode(
    taskId: TaskId,
    constraints: {
      availableSkills: Array<{ level: string; count: number }>
      availableWorkCells: string[]
      prioritizeSpeed?: boolean
    },
  ): Promise<TaskMode | null> {
    try {
      // Get all modes for the task
      const taskModes = await this.findByTaskId(taskId)

      if (taskModes.length === 0) {
        return null
      }

      // Filter modes that can be executed with available resources
      const feasibleModes = taskModes.filter(
        (mode) =>
          mode.canBeExecutedByOperators(constraints.availableSkills) &&
          mode.canBeExecutedInWorkCells(constraints.availableWorkCells),
      )

      if (feasibleModes.length === 0) {
        return null
      }

      if (feasibleModes.length === 1) {
        return feasibleModes[0]
      }

      // Select best mode based on criteria
      return feasibleModes.reduce((best, current) =>
        current.shouldBeSelectedOver(best, {
          prioritizeSpeed: constraints.prioritizeSpeed,
          preferPrimaryMode: true,
        })
          ? current
          : best,
      )
    } catch (error) {
      throw new Error(`TaskMode repository error finding optimal mode: ${error}`)
    }
  }

  async findRequiringExpertSkills(): Promise<TaskMode[]> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements!inner(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .eq('task_mode_skill_requirements.skill_level', 'expert')

      if (error) {
        throw new Error(`Failed to find expert-level task modes: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding expert modes: ${error}`)
    }
  }

  async findByDurationRange(minMinutes: number, maxMinutes: number): Promise<TaskMode[]> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .gte('duration_minutes', minMinutes)
        .lte('duration_minutes', maxMinutes)
        .order('duration_minutes', { ascending: true })

      if (error) {
        throw new Error(`Failed to find task modes by duration range: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding modes by duration: ${error}`)
    }
  }

  async findFastestModesByTaskIds(taskIds: TaskId[]): Promise<Map<string, TaskMode>> {
    try {
      const taskIdStrings = taskIds.map((id) => id.toString())

      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .in('task_id', taskIdStrings)
        .order('duration_minutes', { ascending: true })

      if (error) {
        throw new Error(`Failed to find fastest modes: ${error.message}`)
      }

      const result = new Map<string, TaskMode>()
      const modesByTask = new Map<string, TaskMode[]>()

      // Group modes by task
      for (const row of data) {
        const taskId = row.task_id
        if (!modesByTask.has(taskId)) {
          modesByTask.set(taskId, [])
        }
        modesByTask.get(taskId)!.push(this.mapToDomain(row))
      }

      // Find fastest mode for each task
      for (const [taskId, modes] of modesByTask) {
        const fastestMode = modes.reduce((fastest, current) =>
          current.duration.minutes < fastest.duration.minutes ? current : fastest,
        )
        result.set(taskId, fastestMode)
      }

      return result
    } catch (error) {
      throw new Error(`TaskMode repository error finding fastest modes: ${error}`)
    }
  }

  async findAlternativeModesByTaskIds(taskIds: TaskId[]): Promise<TaskMode[]> {
    try {
      const taskIdStrings = taskIds.map((id) => id.toString())

      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .in('task_id', taskIdStrings)
        .eq('is_primary_mode', false)

      if (error) {
        throw new Error(`Failed to find alternative modes: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding alternative modes: ${error}`)
    }
  }

  async save(taskMode: TaskMode): Promise<TaskMode> {
    try {
      // Start transaction for atomic operation
      const { data: _taskModeData, error: taskModeError } = await this.supabase
        .from('task_modes')
        .upsert(this.mapTaskModeToDatabase(taskMode))
        .select()
        .single()

      if (taskModeError) {
        throw new Error(`Failed to save task mode: ${taskModeError.message}`)
      }

      // Save skill requirements
      await this.saveSkillRequirements(taskMode)

      // Save WorkCell requirements
      await this.saveWorkCellRequirements(taskMode)

      return taskMode
    } catch (error) {
      throw new Error(
        `TaskMode repository error saving task mode ${taskMode.id.toString()}: ${error}`,
      )
    }
  }

  async delete(id: TaskModeId): Promise<boolean> {
    try {
      const { error } = await this.supabase.from('task_modes').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete task mode ${id.toString()}: ${error.message}`)
      }

      return true
    } catch (error) {
      throw new Error(`TaskMode repository error deleting task mode ${id.toString()}: ${error}`)
    }
  }

  async deleteByTaskId(taskId: TaskId): Promise<number> {
    try {
      const { data, error } = await this.supabase
        .from('task_modes')
        .delete()
        .eq('task_id', taskId.toString())
        .select()

      if (error) {
        throw new Error(
          `Failed to delete task modes for task ${taskId.toString()}: ${error.message}`,
        )
      }

      return data.length
    } catch (error) {
      throw new Error(
        `TaskMode repository error deleting modes for task ${taskId.toString()}: ${error}`,
      )
    }
  }

  async saveMany(taskModes: TaskMode[]): Promise<TaskMode[]> {
    try {
      // Save all task modes
      const { data: _data, error } = await this.supabase
        .from('task_modes')
        .upsert(taskModes.map((mode) => this.mapTaskModeToDatabase(mode)))
        .select()

      if (error) {
        throw new Error(`Failed to save multiple task modes: ${error.message}`)
      }

      // Save all skill and WorkCell requirements
      await Promise.all([
        ...taskModes.map((mode) => this.saveSkillRequirements(mode)),
        ...taskModes.map((mode) => this.saveWorkCellRequirements(mode)),
      ])

      return taskModes
    } catch (error) {
      throw new Error(`TaskMode repository error saving multiple modes: ${error}`)
    }
  }

  async getStatistics(): Promise<{
    totalModes: number
    modesByType: Record<string, number>
    averageDurationByType: Record<string, number>
    tasksWithMultipleModes: number
    tasksWithSingleMode: number
  }> {
    try {
      // Get total count and mode statistics
      const { data: stats, error } = await this.supabase
        .from('task_modes')
        .select('type, duration_minutes, task_id')

      if (error) {
        throw new Error(`Failed to get statistics: ${error.message}`)
      }

      const totalModes = stats.length
      const modesByType: Record<string, number> = {}
      const durationsByType: Record<string, number[]> = {}
      const taskModeCount: Record<string, number> = {}

      for (const row of stats) {
        // Count by type
        modesByType[row.type] = (modesByType[row.type] || 0) + 1

        // Track durations by type
        if (!durationsByType[row.type]) {
          durationsByType[row.type] = []
        }
        durationsByType[row.type].push(row.duration_minutes)

        // Count modes per task
        taskModeCount[row.task_id] = (taskModeCount[row.task_id] || 0) + 1
      }

      // Calculate average durations
      const averageDurationByType: Record<string, number> = {}
      for (const [type, durations] of Object.entries(durationsByType)) {
        averageDurationByType[type] = durations.reduce((sum, d) => sum + d, 0) / durations.length
      }

      // Count tasks with multiple vs single modes
      const taskCounts = Object.values(taskModeCount)
      const tasksWithMultipleModes = taskCounts.filter((count) => count > 1).length
      const tasksWithSingleMode = taskCounts.filter((count) => count === 1).length

      return {
        totalModes,
        modesByType,
        averageDurationByType,
        tasksWithMultipleModes,
        tasksWithSingleMode,
      }
    } catch (error) {
      throw new Error(`TaskMode repository error getting statistics: ${error}`)
    }
  }

  async findPaginated(
    limit: number,
    offset: number,
  ): Promise<{
    taskModes: TaskMode[]
    total: number
    hasMore: boolean
  }> {
    try {
      // Get total count
      const { count, error: countError } = await this.supabase
        .from('task_modes')
        .select('*', { count: 'exact', head: true })

      if (countError) {
        throw new Error(`Failed to count task modes: ${countError.message}`)
      }

      // Get paginated results
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .order('name', { ascending: true })
        .range(offset, offset + limit - 1)

      if (error) {
        throw new Error(`Failed to fetch paginated task modes: ${error.message}`)
      }

      const taskModes = data.map((row) => this.mapToDomain(row))
      const total = count || 0
      const hasMore = offset + limit < total

      return { taskModes, total, hasMore }
    } catch (error) {
      throw new Error(`TaskMode repository error finding paginated modes: ${error}`)
    }
  }

  async count(): Promise<number> {
    try {
      const { count, error } = await this.supabase
        .from('task_modes')
        .select('*', { count: 'exact', head: true })

      if (error) {
        throw new Error(`Failed to count task modes: ${error.message}`)
      }

      return count || 0
    } catch (error) {
      throw new Error(`TaskMode repository error counting modes: ${error}`)
    }
  }

  async findTasksWithoutModes(): Promise<string[]> {
    try {
      // Find tasks that don't have any modes
      const { data, error } = await this.supabase
        .from('tasks')
        .select('id')
        .not('id', 'in', this.supabase.from('task_modes').select('task_id'))

      if (error) {
        throw new Error(`Failed to find tasks without modes: ${error.message}`)
      }

      return data.map((row) => row.id)
    } catch (error) {
      throw new Error(`TaskMode repository error finding tasks without modes: ${error}`)
    }
  }

  async findTasksWithMultipleModes(): Promise<Array<{ taskId: string; modeCount: number }>> {
    try {
      const { data, error } = await this.supabase.from('task_modes').select('task_id')

      if (error) {
        throw new Error(`Failed to find tasks with multiple modes: ${error.message}`)
      }

      // Count modes per task
      const taskModeCounts: Record<string, number> = {}
      for (const row of data) {
        taskModeCounts[row.task_id] = (taskModeCounts[row.task_id] || 0) + 1
      }

      // Return only tasks with multiple modes
      return Object.entries(taskModeCounts)
        .filter(([_, count]) => count > 1)
        .map(([taskId, modeCount]) => ({ taskId, modeCount }))
    } catch (error) {
      throw new Error(`TaskMode repository error finding tasks with multiple modes: ${error}`)
    }
  }

  /**
   * Map database row to domain TaskMode entity
   */
  private mapToDomain(
    row: Record<string, unknown> & {
      task_mode_skill_requirements?: SkillRequirementRow[]
      task_mode_workcell_requirements?: WorkCellRequirementRow[]
    },
  ): TaskMode {
    const skillRequirements = (row.task_mode_skill_requirements || []).map(
      (req: SkillRequirementRow) =>
        SkillLevel.create(
          req.skill_level as 'basic' | 'competent' | 'proficient' | 'expert',
          req.quantity,
        ),
    )

    const workCellRequirements = (row.task_mode_workcell_requirements || []).map(
      (req: WorkCellRequirementRow) => WorkCellId.create(req.workcell_id),
    )

    return TaskMode.fromPersistence({
      id: TaskModeId.create(row.id),
      taskId: TaskId.fromString(row.task_id),
      name: TaskModeName.create(row.name),
      type: TaskModeType.create(row.type as TaskModeTypeValue),
      duration: TaskModeDuration.create(row.duration_minutes),
      isPrimaryMode: row.is_primary_mode,
      skillRequirements,
      workCellRequirements,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: row.version,
    })
  }

  /**
   * Map TaskMode entity to database row
   */
  private mapTaskModeToDatabase(taskMode: TaskMode): TaskModeInsert {
    return {
      id: taskMode.id.toString(),
      task_id: taskMode.taskId.toString(),
      name: taskMode.name.toString(),
      type: taskMode.type.value,
      duration_minutes: taskMode.duration.minutes,
      is_primary_mode: taskMode.isPrimaryMode,
      created_at: taskMode.createdAt.toISOString(),
      updated_at: new Date().toISOString(),
      version: taskMode.version,
    }
  }

  /**
   * Save skill requirements for a TaskMode
   */
  private async saveSkillRequirements(taskMode: TaskMode): Promise<void> {
    // Delete existing requirements
    await this.supabase
      .from('task_mode_skill_requirements')
      .delete()
      .eq('task_mode_id', taskMode.id.toString())

    if (taskMode.skillRequirements.length === 0) {
      return
    }

    // Insert new requirements
    const skillData = taskMode.skillRequirements.map((skill) => ({
      task_mode_id: taskMode.id.toString(),
      skill_level: skill.level,
      quantity: skill.quantity,
    }))

    const { error } = await this.supabase.from('task_mode_skill_requirements').insert(skillData)

    if (error) {
      throw new Error(`Failed to save skill requirements: ${error.message}`)
    }
  }

  /**
   * Save WorkCell requirements for a TaskMode
   */
  private async saveWorkCellRequirements(taskMode: TaskMode): Promise<void> {
    // Delete existing requirements
    await this.supabase
      .from('task_mode_workcell_requirements')
      .delete()
      .eq('task_mode_id', taskMode.id.toString())

    if (taskMode.workCellRequirements.length === 0) {
      return
    }

    // Insert new requirements
    const workCellData = taskMode.workCellRequirements.map((workCell) => ({
      task_mode_id: taskMode.id.toString(),
      workcell_id: workCell.toString(),
    }))

    const { error } = await this.supabase
      .from('task_mode_workcell_requirements')
      .insert(workCellData)

    if (error) {
      throw new Error(`Failed to save WorkCell requirements: ${error.message}`)
    }
  }

  /**
   * OPTIMIZATION: Batch loading TaskModes for multiple tasks
   * Prevents N+1 queries when loading task-taskmode relationships
   */
  async findByTaskIds(taskIds: TaskId[]): Promise<Map<string, TaskMode[]>> {
    try {
      if (taskIds.length === 0) {
        return new Map()
      }

      const taskIdStrings = taskIds.map((id) => id.toString())
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .in('task_id', taskIdStrings)
        .order('task_id', { ascending: true })
        .order('is_primary_mode', { ascending: false })

      if (error) {
        throw new Error(`Failed to batch load task modes by task IDs: ${error.message}`)
      }

      // Group modes by task ID
      const modesByTask = new Map<string, TaskMode[]>()

      data.forEach((row) => {
        const taskId = row.task_id
        if (!modesByTask.has(taskId)) {
          modesByTask.set(taskId, [])
        }
        modesByTask.get(taskId)!.push(this.mapToDomain(row))
      })

      return modesByTask
    } catch (error) {
      throw new Error(`TaskMode repository error in batch loading by task IDs: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Find primary TaskModes for multiple tasks efficiently
   * Single query for manufacturing scheduling operations
   */
  async findPrimaryModesByTaskIds(taskIds: TaskId[]): Promise<Map<string, TaskMode>> {
    try {
      if (taskIds.length === 0) {
        return new Map()
      }

      const taskIdStrings = taskIds.map((id) => id.toString())
      const { data, error } = await this.supabase
        .from('task_modes')
        .select(
          `
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `,
        )
        .in('task_id', taskIdStrings)
        .eq('is_primary_mode', true)

      if (error) {
        throw new Error(`Failed to batch load primary task modes: ${error.message}`)
      }

      const primaryModesByTask = new Map<string, TaskMode>()

      data.forEach((row) => {
        const taskMode = this.mapToDomain(row)
        primaryModesByTask.set(row.task_id, taskMode)
      })

      return primaryModesByTask
    } catch (error) {
      throw new Error(`TaskMode repository error finding primary modes: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Bulk operations for manufacturing resource planning
   */
  async findModesWithResourceConstraints(
    maxDurationMinutes?: number,
    requiredSkillLevels?: string[],
    requiredWorkCells?: string[],
  ): Promise<TaskMode[]> {
    try {
      let query = this.supabase.from('task_modes').select(`
          *,
          task_mode_skill_requirements(*),
          task_mode_workcell_requirements(*)
        `)

      if (maxDurationMinutes) {
        query = query.lte('duration_minutes', maxDurationMinutes)
      }

      if (requiredSkillLevels && requiredSkillLevels.length > 0) {
        query = query.filter(
          'task_mode_skill_requirements.skill_level',
          'in',
          `(${requiredSkillLevels.join(',')})`,
        )
      }

      if (requiredWorkCells && requiredWorkCells.length > 0) {
        query = query.filter(
          'task_mode_workcell_requirements.workcell_id',
          'in',
          `(${requiredWorkCells.join(',')})`,
        )
      }

      const { data, error } = await query.order('duration_minutes', { ascending: true })

      if (error) {
        throw new Error(`Failed to find modes with resource constraints: ${error.message}`)
      }

      return data.map((row) => this.mapToDomain(row))
    } catch (error) {
      throw new Error(`TaskMode repository error finding resource constrained modes: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Analytics for manufacturing capacity planning
   */
  async getResourceUtilizationAnalytics(): Promise<{
    modesByWorkCell: Map<string, number>
    modesBySkillLevel: Map<string, number>
    averageDurationByType: Map<string, number>
    capacityBottlenecks: Array<{
      resource: string
      type: 'workcell' | 'skill'
      demandCount: number
    }>
  }> {
    try {
      const { data: modes, error: modesError } = await this.supabase
        .from('task_modes')
        .select('type, duration_minutes')

      if (modesError) {
        throw new Error(`Failed to get mode analytics: ${modesError.message}`)
      }

      const { data: skillReqs, error: skillError } = await this.supabase
        .from('task_mode_skill_requirements')
        .select('skill_level, quantity')

      if (skillError) {
        throw new Error(`Failed to get skill requirements: ${skillError.message}`)
      }

      const { data: workCellReqs, error: workCellError } = await this.supabase
        .from('task_mode_workcell_requirements')
        .select('workcell_id')

      if (workCellError) {
        throw new Error(`Failed to get workcell requirements: ${workCellError.message}`)
      }

      // Aggregate data for analytics
      const modesByWorkCell = new Map<string, number>()
      const modesBySkillLevel = new Map<string, number>()
      const durationsByType = new Map<string, number[]>()

      // Count WorkCell usage
      workCellReqs.forEach((req) => {
        const count = modesByWorkCell.get(req.workcell_id) || 0
        modesByWorkCell.set(req.workcell_id, count + 1)
      })

      // Count skill level usage
      skillReqs.forEach((req) => {
        const count = modesBySkillLevel.get(req.skill_level) || 0
        modesBySkillLevel.set(req.skill_level, count + req.quantity)
      })

      // Calculate average durations by type
      modes.forEach((mode) => {
        if (!durationsByType.has(mode.type)) {
          durationsByType.set(mode.type, [])
        }
        durationsByType.get(mode.type)!.push(mode.duration_minutes)
      })

      const averageDurationByType = new Map<string, number>()
      durationsByType.forEach((durations, type) => {
        const average = durations.reduce((sum, d) => sum + d, 0) / durations.length
        averageDurationByType.set(type, average)
      })

      // Identify capacity bottlenecks (top 5 most demanded resources)
      const capacityBottlenecks = [
        ...Array.from(modesByWorkCell.entries()).map(([resource, count]) => ({
          resource,
          type: 'workcell' as const,
          demandCount: count,
        })),
        ...Array.from(modesBySkillLevel.entries()).map(([resource, count]) => ({
          resource,
          type: 'skill' as const,
          demandCount: count,
        })),
      ]
        .sort((a, b) => b.demandCount - a.demandCount)
        .slice(0, 5)

      return {
        modesByWorkCell,
        modesBySkillLevel,
        averageDurationByType,
        capacityBottlenecks,
      }
    } catch (error) {
      throw new Error(`TaskMode repository error getting analytics: ${error}`)
    }
  }
}
