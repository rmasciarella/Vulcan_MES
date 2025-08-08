import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database, Tables } from '@/types/supabase'
import type { SolvedSchedule, SolvedScheduleInsert, SolvedScheduleUpdate, ScheduledTask } from '@/core/types/database'

type ScheduleRow = Tables['solved_schedules']['Row']
type ScheduleInsert = Database['public']['Tables']['solved_schedules']['Insert']
type ScheduleUpdate = Database['public']['Tables']['solved_schedules']['Update']
type ScheduledTaskRow = Tables['scheduled_tasks']['Row']

export interface ScheduleFilters {
  start?: Date
  end?: Date
  solverStatus?: string
}

/**
 * Supabase implementation for schedule operations
 * Handles persistence and querying of Schedule entities
 */
export class SupabaseScheduleRepository {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Find all schedules with optional filters
   */
  async findMany(filters?: ScheduleFilters): Promise<SolvedSchedule[]> {
    let query = this.supabase
      .from('solved_schedules')
      .select('*')
      .order('created_at', { ascending: false })

    if (filters?.start && filters?.end) {
      query = query
        .gte('solution_timestamp', filters.start.toISOString())
        .lte('solution_timestamp', filters.end.toISOString())
    }

    if (filters?.solverStatus) {
      query = query.eq('status', filters.solverStatus)
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch schedules: ${error.message}`)
    }

    return (data as SolvedSchedule[]) ?? []
  }

  /**
   * Find schedule by ID
   */
  async findById(id: string): Promise<SolvedSchedule | null> {
    const { data, error } = await this.supabase
      .from('solved_schedules')
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return null
      }
      throw new Error(`Failed to fetch schedule: ${error.message}`)
    }

    return data as SolvedSchedule
  }

  /**
   * Find scheduled tasks for a schedule
   */
  async findScheduleTasks(scheduleId: string): Promise<ScheduledTask[]> {
    const { data, error } = await this.supabase
      .from('scheduled_tasks')
      .select(
        `
        *,
        job_instance:job_instances(*),
        machine:machines(*),
        operator:operators(*)
      `,
      )
      .eq('schedule_id', scheduleId)
      .order('scheduled_start', { ascending: true })

    if (error) {
      throw new Error(`Failed to fetch schedule tasks: ${error.message}`)
    }

    return (data as ScheduledTask[]) ?? []
  }

  /**
   * Create a new schedule
   */
  async create(schedule: SolvedScheduleInsert): Promise<SolvedSchedule> {
    const { data, error } = await this.supabase
      .from('solved_schedules')
      .insert(schedule)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to create schedule: ${error.message}`)
    }

    return data as SolvedSchedule
  }

  /**
   * Update schedule solver status
   */
  async updateSolverStatus(id: string, solverStatus: string): Promise<SolvedSchedule> {
    const { data, error } = await this.supabase
      .from('solved_schedules')
      .update({ status: solverStatus })
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update schedule status: ${error.message}`)
    }

    return data as SolvedSchedule
  }

  /**
   * Save draft schedule tasks (replace existing)
   */
  async saveDraftScheduleTasks(
    scheduleId: string,
    tasks: ScheduledTask[],
  ): Promise<{ scheduleId: string; taskCount: number }> {
    // Delete existing tasks for this schedule
    const { error: deleteError } = await this.supabase
      .from('scheduled_tasks')
      .delete()
      .eq('schedule_id', scheduleId)

    if (deleteError) {
      throw new Error(`Failed to delete existing tasks: ${deleteError.message}`)
    }

    // Insert new tasks if any
    if (tasks.length > 0) {
      const { error: insertError } = await this.supabase
        .from('scheduled_tasks')
        .insert(tasks.map((task) => ({ ...task, schedule_id: scheduleId })))

      if (insertError) {
        throw new Error(`Failed to insert tasks: ${insertError.message}`)
      }
    }

    return { scheduleId, taskCount: tasks.length }
  }

  /**
   * Check if schedule exists
   */
  async exists(id: string): Promise<boolean> {
    const { data, error } = await this.supabase
      .from('solved_schedules')
      .select('id')
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return false
      }
      throw new Error(`Failed to check schedule existence: ${error.message}`)
    }

    return data !== null
  }

  /**
   * Delete schedule by ID
   */
  async delete(id: string): Promise<void> {
    const { error } = await this.supabase.from('solved_schedules').delete().eq('id', id)

    if (error) {
      throw new Error(`Failed to delete schedule: ${error.message}`)
    }
  }
}