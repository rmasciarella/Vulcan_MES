import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import { Job } from '@/core/domains/jobs/job'
import { Task } from '@/core/domains/tasks/task'
import { TaskMode } from '@/core/domains/tasks/entities/TaskMode'
import { JobId, JobStatus } from '@/core/domains/jobs/value-objects'
import { TaskStatus } from '@/core/domains/tasks/value-objects'
import { SupabaseJobRepository } from '@/infrastructure/supabase/repositories/supabase-job-repository'
import { SupabaseTaskRepository } from '@/infrastructure/supabase/repositories/supabase-task-repository'
import { SupabaseTaskModeRepository } from '@/infrastructure/supabase/repositories/supabase-task-mode-repository'
import { domainLogger } from '@/core/shared/logger'

/**
 * Manufacturing Data Service - Optimized cross-domain data loading
 *
 * Designed for manufacturing requirements:
 * - Efficient loading of 1000+ jobs with tasks and modes
 * - Prevention of N+1 queries through strategic batch loading
 * - Memory-efficient data processing with streaming support
 * - Manufacturing-specific query patterns and optimizations
 * - Connection pool management for high-volume operations
 */
export class ManufacturingDataService {
  private readonly jobRepository: SupabaseJobRepository
  private readonly taskRepository: SupabaseTaskRepository
  private readonly taskModeRepository: SupabaseTaskModeRepository

  constructor(private readonly supabase: SupabaseClient<Database>) {
    this.jobRepository = new SupabaseJobRepository(supabase)
    this.taskRepository = new SupabaseTaskRepository(supabase)
    this.taskModeRepository = new SupabaseTaskModeRepository(supabase)
  }

  /**
   * OPTIMIZATION: Load jobs with tasks in minimal queries
   * Prevents N+1 problem for manufacturing dashboard views
   */
  async loadJobsWithTasks(filters?: {
    status?: JobStatus
    startDate?: Date
    endDate?: Date
    limit?: number
    offset?: number
  }): Promise<{
    jobs: Array<{ job: Job; tasks: Task[] }>
    total: number
    hasMore: boolean
  }> {
    try {
      // Step 1: Load jobs with pagination
      const jobsResult = await this.loadJobsWithFilters(filters)

      if (jobsResult.jobs.length === 0) {
        return { jobs: [], total: 0, hasMore: false }
      }

      // Step 2: Batch load tasks for all jobs in single query
      const jobIds = jobsResult.jobs.map((job) => job.id)
      const tasksByJobMap = await this.taskRepository.findByJobIds(jobIds)

      // Step 3: Combine jobs with their tasks
      const jobsWithTasks = jobsResult.jobs.map((job) => ({
        job,
        tasks: tasksByJobMap.get(job.id.toString()) || [],
      }))

      domainLogger.infrastructure.info(
        `Loaded ${jobsResult.jobs.length} jobs with ${Array.from(tasksByJobMap.values()).flat().length} tasks`,
        {
          jobCount: jobsResult.jobs.length,
          taskCount: Array.from(tasksByJobMap.values()).flat().length,
          queriesUsed: 2, // vs N+1 without optimization
        },
      )

      return {
        jobs: jobsWithTasks,
        total: jobsResult.total,
        hasMore: jobsResult.hasMore,
      }
    } catch (error) {
      domainLogger.infrastructure.error('Failed to load jobs with tasks', error as Error)
      throw new Error(`Manufacturing data service error loading jobs with tasks: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Load complete job-task-taskmode hierarchy
   * Single-query approach for manufacturing scheduling operations
   */
  async loadCompleteJobHierarchy(jobIds: JobId[]): Promise<
    Array<{
      job: Job
      tasks: Array<{
        task: Task
        modes: TaskMode[]
        primaryMode: TaskMode | null
      }>
    }>
  > {
    try {
      if (jobIds.length === 0) {
        return []
      }

      // Step 1: Batch load jobs
      const jobs = await this.jobRepository.findByIdsWithBatchLoading(jobIds)

      // Step 2: Batch load tasks for all jobs
      const tasksByJobMap = await this.taskRepository.findByJobIds(jobIds)

      // Step 3: Get all task IDs and batch load task modes
      const allTaskIds = Array.from(tasksByJobMap.values())
        .flat()
        .map((task) => task.id)

      const modesByTaskMap = await this.taskModeRepository.findByTaskIds(allTaskIds)
      const primaryModesByTaskMap =
        await this.taskModeRepository.findPrimaryModesByTaskIds(allTaskIds)

      // Step 4: Assemble complete hierarchy
      const completeHierarchy = jobs.map((job) => {
        const jobTasks = tasksByJobMap.get(job.id.toString()) || []

        const tasksWithModes = jobTasks.map((task) => ({
          task,
          modes: modesByTaskMap.get(task.id.toString()) || [],
          primaryMode: primaryModesByTaskMap.get(task.id.toString()) || null,
        }))

        return {
          job,
          tasks: tasksWithModes,
        }
      })

      const totalTasks = Array.from(tasksByJobMap.values()).flat().length
      const totalModes = Array.from(modesByTaskMap.values()).flat().length

      domainLogger.infrastructure.info(
        `Loaded complete job hierarchy: ${jobs.length} jobs, ${totalTasks} tasks, ${totalModes} modes`,
        {
          jobCount: jobs.length,
          taskCount: totalTasks,
          modeCount: totalModes,
          queriesUsed: 4, // vs N*M+1 without optimization
        },
      )

      return completeHierarchy
    } catch (error) {
      domainLogger.infrastructure.error('Failed to load complete job hierarchy', error as Error)
      throw new Error(`Manufacturing data service error loading job hierarchy: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Load schedulable tasks with resource information
   * Manufacturing scheduling optimization with resource constraints
   */
  async loadSchedulableTasks(): Promise<
    Array<{
      job: { id: string; dueDate: Date; status: string }
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
      // Single optimized query for schedulable tasks with resource info
      const schedulableTasksWithModes = await this.taskRepository.findSchedulableWithResourceInfo()

      // Batch load minimal job information for scheduling context
      const jobIds = [...new Set(schedulableTasksWithModes.map((item) => item.task.jobId))]
      const jobs = await this.jobRepository.findByIdsWithBatchLoading(jobIds)
      const jobsMap = new Map(jobs.map((job) => [job.id.toString(), job]))

      const result = schedulableTasksWithModes.map((item) => {
        const job = jobsMap.get(item.task.jobId.toString())
        return {
          job: job
            ? {
                id: job.id.toString(),
                dueDate: job.dueDate.toDate(),
                status: job.status.getValue(),
              }
            : {
                id: item.task.jobId.toString(),
                dueDate: new Date(),
                status: 'UNKNOWN',
              },
          task: item.task,
          primaryMode: item.primaryMode,
        }
      })

      domainLogger.infrastructure.info(
        `Loaded ${result.length} schedulable tasks from ${jobIds.length} jobs`,
        {
          schedulableTaskCount: result.length,
          jobCount: jobIds.length,
          queriesUsed: 2,
        },
      )

      return result
    } catch (error) {
      domainLogger.infrastructure.error('Failed to load schedulable tasks', error as Error)
      throw new Error(`Manufacturing data service error loading schedulable tasks: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Manufacturing analytics dashboard data
   * Aggregated metrics for manufacturing performance monitoring
   */
  async getManufacturingMetrics(): Promise<{
    jobMetrics: {
      totalJobs: number
      jobsByStatus: Record<string, number>
      averageJobsPerDay: number
      overdueJobs: number
    }
    taskMetrics: {
      totalTasks: number
      tasksByStatus: Record<string, number>
      averageTasksPerJob: number
      setupTaskRatio: number
      unattendedTaskRatio: number
    }
    resourceMetrics: {
      modesByWorkCell: Map<string, number>
      modesBySkillLevel: Map<string, number>
      averageDurationByType: Map<string, number>
      capacityBottlenecks: Array<{
        resource: string
        type: 'workcell' | 'skill'
        demandCount: number
      }>
    }
  }> {
    try {
      // Parallel execution of analytics queries for optimal performance
      const [jobCount, jobStatusDistribution, taskMetrics, resourceAnalytics] = await Promise.all([
        this.jobRepository.count(),
        this.getJobStatusDistribution(),
        this.taskRepository.getPerformanceMetrics(),
        this.taskModeRepository.getResourceUtilizationAnalytics(),
      ])

      // Calculate derived metrics
      const now = new Date()
      const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      const recentJobCount = await this.jobRepository.countByStatusAndDateRange(
        undefined, // any status
        thirtyDaysAgo,
        now,
      )
      const averageJobsPerDay = recentJobCount / 30

      // Calculate overdue jobs (simplified - should use proper scheduling data)
      const overdueJobs = await this.jobRepository.countByStatusAndDateRange(
        JobStatus.create('SCHEDULED'),
        undefined,
        new Date(), // past due date
      )

      const result = {
        jobMetrics: {
          totalJobs: jobCount,
          jobsByStatus: jobStatusDistribution,
          averageJobsPerDay,
          overdueJobs,
        },
        taskMetrics,
        resourceMetrics: resourceAnalytics,
      }

      domainLogger.infrastructure.info('Generated manufacturing metrics', {
        totalJobs: result.jobMetrics.totalJobs,
        totalTasks: result.taskMetrics.totalTasks,
        resourceTypes: Array.from(result.resourceMetrics.modesByWorkCell.keys()).length,
      })

      return result
    } catch (error) {
      domainLogger.infrastructure.error('Failed to get manufacturing metrics', error as Error)
      throw new Error(`Manufacturing data service error getting metrics: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Bulk status updates for manufacturing batch operations
   */
  async bulkUpdateJobStatus(
    jobIds: JobId[],
    newStatus: JobStatus,
  ): Promise<{
    jobsUpdated: number
    tasksUpdated: number
  }> {
    try {
      // Update jobs in batch
      const updatedJobs = await this.jobRepository.bulkSave(
        (await this.jobRepository.findByIdsWithBatchLoading(jobIds)).map((job) => {
          job.updateStatus(newStatus.getValue())
          return job
        }),
      )

      // Update related tasks if needed (e.g., when job becomes IN_PROGRESS)
      let tasksUpdated = 0
      if (newStatus.getValue() === 'IN_PROGRESS') {
        const tasksByJob = await this.taskRepository.findByJobIds(jobIds)
        const readyTasks = Array.from(tasksByJob.values())
          .flat()
          .filter((task) => task.status.value === 'ready')
          .slice(0, 1) // Start first task only

        if (readyTasks.length > 0) {
          const firstTaskIds = readyTasks.map((task) => task.id)
          tasksUpdated = await this.taskRepository.bulkUpdateStatus(
            firstTaskIds,
            TaskStatus.create('in_progress'),
          )
        }
      }

      domainLogger.infrastructure.info(
        `Bulk status update completed: ${updatedJobs.length} jobs, ${tasksUpdated} tasks`,
        {
          jobIds: jobIds.map((id) => id.toString()),
          newStatus: newStatus.getValue(),
          jobsUpdated: updatedJobs.length,
          tasksUpdated,
        },
      )

      return {
        jobsUpdated: updatedJobs.length,
        tasksUpdated,
      }
    } catch (error) {
      domainLogger.infrastructure.error('Failed bulk status update', error as Error)
      throw new Error(`Manufacturing data service error in bulk update: ${error}`)
    }
  }

  /**
   * OPTIMIZATION: Clear all repository caches periodically
   * Prevents memory leaks during long-running manufacturing operations
   */
  clearAllCaches(): void {
    this.taskRepository.clearDataCaches()
    domainLogger.infrastructure.info('Cleared all manufacturing data caches')
  }

  /**
   * Private helper to load jobs with filters efficiently
   */
  private async loadJobsWithFilters(filters?: {
    status?: JobStatus
    startDate?: Date
    endDate?: Date
    limit?: number
    offset?: number
  }): Promise<{ jobs: Job[]; total: number; hasMore: boolean }> {
    const limit = filters?.limit || 500 // Manufacturing batch size
    const offset = filters?.offset || 0

    if (filters?.status) {
      const jobs = await this.jobRepository.findByStatusWithOptionalTasks(
        filters.status,
        false, // Don't load tasks yet - will batch load separately
      )

      // Apply additional filters in memory (could be optimized to database level)
      let filteredJobs = jobs
      if (filters.startDate || filters.endDate) {
        filteredJobs = jobs.filter((job) => {
          const dueDate = job.dueDate.toDate()
          return (
            (!filters.startDate || dueDate >= filters.startDate) &&
            (!filters.endDate || dueDate <= filters.endDate)
          )
        })
      }

      // Apply pagination
      const paginatedJobs = filteredJobs.slice(offset, offset + limit)
      const hasMore = offset + limit < filteredJobs.length

      return {
        jobs: paginatedJobs,
        total: filteredJobs.length,
        hasMore,
      }
    }

    // Use general paginated query
    return this.jobRepository.findPaginated(limit, offset)
  }

  /**
   * Helper to get job status distribution
   */
  private async getJobStatusDistribution(): Promise<Record<string, number>> {
    try {
      const { data, error } = await this.supabase.from('job_instances').select('status')

      if (error) {
        throw new Error(`Failed to get job status distribution: ${error.message}`)
      }

      const distribution: Record<string, number> = {}
      data.forEach((row) => {
        distribution[row.status] = (distribution[row.status] || 0) + 1
      })

      return distribution
    } catch (error) {
      throw new Error(`Failed to analyze job status distribution: ${error}`)
    }
  }
}

/**
 * Factory function for creating ManufacturingDataService instances
 * Ensures proper dependency injection and configuration
 */
export function createManufacturingDataService(
  supabase: SupabaseClient<Database>,
): ManufacturingDataService {
  return new ManufacturingDataService(supabase)
}
