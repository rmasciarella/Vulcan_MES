import type { SolvedSchedule, SolvedScheduleInsert, ScheduledTask } from '@/core/types/database'
import type { SupabaseScheduleRepository, ScheduleFilters } from '@/infrastructure/supabase/repositories/supabase-schedule-repository'

import type { UseCases } from '@vulcan/domain'

export interface ScheduleUseCases extends UseCases.IScheduleUseCases<SolvedSchedule, string, ScheduledTask> {}

/**
 * Implementation of schedule use cases using the repository pattern
 */
export class ScheduleUseCasesImpl implements ScheduleUseCases {
  constructor(private readonly scheduleRepository: SupabaseScheduleRepository) {}

  async fetchSchedules(filters?: ScheduleFilters): Promise<SolvedSchedule[]> {
    try {
      return await this.scheduleRepository.findMany(filters)
    } catch (error) {
      throw new Error(`Failed to fetch schedules: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async fetchScheduleById(id: string): Promise<SolvedSchedule | null> {
    if (!id) {
      throw new Error('Schedule ID is required')
    }

    try {
      return await this.scheduleRepository.findById(id)
    } catch (error) {
      throw new Error(`Failed to fetch schedule ${id}: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async fetchScheduleTasks(scheduleId: string): Promise<ScheduledTask[]> {
    if (!scheduleId) {
      throw new Error('Schedule ID is required')
    }

    try {
      return await this.scheduleRepository.findScheduleTasks(scheduleId)
    } catch (error) {
      throw new Error(`Failed to fetch schedule tasks: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async createSchedule(schedule: SolvedScheduleInsert): Promise<SolvedSchedule> {
    if (!schedule) {
      throw new Error('Schedule data is required')
    }

    try {
      return await this.scheduleRepository.create(schedule)
    } catch (error) {
      throw new Error(`Failed to create schedule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async updateScheduleSolverStatus(id: string, solverStatus: string): Promise<SolvedSchedule> {
    if (!id) {
      throw new Error('Schedule ID is required')
    }
    if (!solverStatus) {
      throw new Error('Solver status is required')
    }

    try {
      return await this.scheduleRepository.updateSolverStatus(id, solverStatus)
    } catch (error) {
      throw new Error(`Failed to update schedule status: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async saveDraftSchedule(
    scheduleId: string,
    tasks: ScheduledTask[],
  ): Promise<{ scheduleId: string; taskCount: number }> {
    if (!scheduleId) {
      throw new Error('Schedule ID is required')
    }
    if (!Array.isArray(tasks)) {
      throw new Error('Tasks must be an array')
    }

    try {
      return await this.scheduleRepository.saveDraftScheduleTasks(scheduleId, tasks)
    } catch (error) {
      throw new Error(`Failed to save draft schedule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  async deleteSchedule(id: string): Promise<void> {
    if (!id) {
      throw new Error('Schedule ID is required')
    }

    try {
      await this.scheduleRepository.delete(id)
    } catch (error) {
      throw new Error(`Failed to delete schedule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }
}