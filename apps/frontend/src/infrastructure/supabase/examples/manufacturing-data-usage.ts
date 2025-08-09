/**
 * Manufacturing Data Pipeline Usage Examples
 * Demonstrates optimized data loading patterns for 1000+ concurrent jobs
 */

import { getManufacturingDataPipeline } from '@/infrastructure/supabase/config/data-pipeline-config'
// TODO: Fix imports after migration
// import { JobStatus } from '@/core/domains/jobs/value-objects'
// import { TaskStatus, TaskId } from '@/core/domains/tasks/value-objects'

/**
 * Example 1: Efficient Dashboard Data Loading
 * Load jobs with tasks in minimal queries for manufacturing dashboard
 */
export async function loadManufacturingDashboard() {
  const pipeline = getManufacturingDataPipeline()
  const dataService = pipeline.getDataService()

  try {
    console.log('🏭 Loading manufacturing dashboard data...')

    // Load active jobs with their tasks in 2 queries instead of N+1
    const result = await pipeline.executeBatchOperation('dashboard-jobs-with-tasks', () =>
      dataService.loadJobsWithTasks({
        status: JobStatus.create('IN_PROGRESS'),
        limit: 100, // Dashboard view
      }),
    )

    console.log(`✅ Loaded ${result.jobs.length} jobs with tasks`)
    console.log(`📊 Total tasks: ${result.jobs.reduce((sum, item) => sum + item.tasks.length, 0)}`)

    return result
  } catch (error) {
    console.error('❌ Dashboard loading failed:', error)
    throw error
  }
}

/**
 * Example 2: Manufacturing Scheduling Optimization
 * Load schedulable tasks with resource requirements for OR-Tools scheduling
 */
export async function loadSchedulingData() {
  const pipeline = getManufacturingDataPipeline()
  const dataService = pipeline.getDataService()

  try {
    console.log('📅 Loading scheduling data...')

    // Single optimized query for all schedulable tasks with resource info
    const schedulableTasks = await pipeline.executeBatchOperation(
      'scheduling-tasks-with-resources',
      () => dataService.loadSchedulableTasks(),
    )

    console.log(`✅ Loaded ${schedulableTasks.length} schedulable tasks`)

    // Group by resource requirements for scheduling optimization
    const tasksByWorkCell = new Map<string, typeof schedulableTasks>()
    const tasksBySkillLevel = new Map<string, typeof schedulableTasks>()

    schedulableTasks.forEach((item) => {
      if (item.primaryMode) {
        // Group by WorkCell requirements
        item.primaryMode.workCellRequirements.forEach((workCellId) => {
          if (!tasksByWorkCell.has(workCellId)) {
            tasksByWorkCell.set(workCellId, [])
          }
          tasksByWorkCell.get(workCellId)!.push(item)
        })

        // Group by skill requirements
        item.primaryMode.skillRequirements.forEach((skill) => {
          if (!tasksBySkillLevel.has(skill.level)) {
            tasksBySkillLevel.set(skill.level, [])
          }
          tasksBySkillLevel.get(skill.level)!.push(item)
        })
      }
    })

    console.log(`📈 Resource distribution:`)
    console.log(`   WorkCells: ${tasksByWorkCell.size}`)
    console.log(`   Skill levels: ${tasksBySkillLevel.size}`)

    return {
      schedulableTasks,
      tasksByWorkCell,
      tasksBySkillLevel,
    }
  } catch (error) {
    console.error('❌ Scheduling data loading failed:', error)
    throw error
  }
}

/**
 * Example 3: Bulk Job Processing
 * Process large batches of jobs efficiently for manufacturing operations
 */
export async function processBulkJobOperations() {
  const pipeline = getManufacturingDataPipeline()
  const dataService = pipeline.getDataService()
  const repositories = pipeline.getRepositories()

  try {
    console.log('⚙️ Processing bulk job operations...')

    // Load jobs in batches for processing
    const jobBatch = await repositories.jobs.findPaginated(500, 0) // Optimal batch size

    // Simulate bulk status update (e.g., Monday morning job release)
    const draftJobIds = jobBatch.jobs
      .filter((job) => job.status.getValue() === 'DRAFT')
      .slice(0, 50) // Limit for example
      .map((job) => job.id)

    if (draftJobIds.length > 0) {
      console.log(`🚀 Releasing ${draftJobIds.length} jobs...`)

      const updateResult = await pipeline.executeBatchOperation('bulk-job-release', () =>
        dataService.bulkUpdateJobStatus(draftJobIds, JobStatus.create('SCHEDULED')),
      )

      console.log(`✅ Updated ${updateResult.jobsUpdated} jobs, ${updateResult.tasksUpdated} tasks`)
    }

    // Load complete job hierarchy for complex operations
    const sampleJobIds = jobBatch.jobs.slice(0, 10).map((job) => job.id)
    const completeHierarchy = await pipeline.executeBatchOperation('complete-job-hierarchy', () =>
      dataService.loadCompleteJobHierarchy(sampleJobIds),
    )

    console.log(`🏗️ Loaded complete hierarchy for ${completeHierarchy.length} jobs`)
    completeHierarchy.forEach((item) => {
      console.log(`   Job ${item.job.serialNumber.toString()}: ${item.tasks.length} tasks`)
    })

    return completeHierarchy
  } catch (error) {
    console.error('❌ Bulk processing failed:', error)
    throw error
  }
}

/**
 * Example 4: Performance Monitoring and Analytics
 * Monitor and analyze manufacturing data pipeline performance
 */
export async function monitorPerformance() {
  const pipeline = getManufacturingDataPipeline()
  const performanceMonitor = pipeline.getPerformanceMonitor()

  try {
    console.log('📊 Monitoring performance...')

    // Get current performance metrics
    const metrics = performanceMonitor.getPerformanceMetrics()
    console.log(`📈 Query metrics (${metrics.queryMetrics.length} operations):`)

    metrics.queryMetrics.slice(0, 5).forEach((query) => {
      console.log(`   ${query.operation}: ${query.averageTime}ms avg (${query.count} calls)`)
    })

    console.log(`🔌 Connection metrics:`)
    console.log(`   Active: ${metrics.connectionMetrics.activeConnections}`)
    console.log(`   Total queries: ${metrics.connectionMetrics.totalQueries}`)
    console.log(`   Slow queries: ${metrics.connectionMetrics.slowQueries}`)

    if (metrics.recommendations.length > 0) {
      console.log(`💡 Recommendations:`)
      metrics.recommendations.forEach((rec) => console.log(`   - ${rec}`))
    }

    // Check overall health
    const health = await pipeline.healthCheck()
    console.log(`🏥 Pipeline health: ${health.status}`)

    if (health.recommendations.length > 0) {
      console.log(`⚠️ Health issues:`)
      health.recommendations.forEach((issue) => console.log(`   - ${issue}`))
    }

    // Get manufacturing-specific insights
    const insights = performanceMonitor.getManufacturingInsights()
    console.log(`🎯 Manufacturing insights:`)
    console.log(`   Batch efficiency: ${insights.batchOperationEfficiency.toFixed(1)}%`)
    console.log(`   Recommended batch size: ${insights.recommendedBatchSize}`)
    console.log(`   Optimization opportunities: ${insights.optimizationOpportunities.length}`)

    return { metrics, health, insights }
  } catch (error) {
    console.error('❌ Performance monitoring failed:', error)
    throw error
  }
}

/**
 * Example 5: Manufacturing Analytics Dashboard
 * Generate comprehensive metrics for manufacturing operations
 */
export async function generateManufacturingAnalytics() {
  const pipeline = getManufacturingDataPipeline()
  const dataService = pipeline.getDataService()

  try {
    console.log('📊 Generating manufacturing analytics...')

    const analytics = await pipeline.executeBatchOperation('manufacturing-analytics', () =>
      dataService.getManufacturingMetrics(),
    )

    console.log(`🏭 Manufacturing Metrics:`)
    console.log(`   Total Jobs: ${analytics.jobMetrics.totalJobs}`)
    console.log(`   Jobs per day: ${analytics.jobMetrics.averageJobsPerDay.toFixed(1)}`)
    console.log(`   Overdue jobs: ${analytics.jobMetrics.overdueJobs}`)

    console.log(`⚙️ Task Metrics:`)
    console.log(`   Total Tasks: ${analytics.taskMetrics.totalTasks}`)
    console.log(`   Avg tasks/job: ${analytics.taskMetrics.averageTasksPerJob.toFixed(1)}`)
    console.log(`   Setup task ratio: ${(analytics.taskMetrics.setupTaskRatio * 100).toFixed(1)}%`)
    console.log(
      `   Unattended ratio: ${(analytics.taskMetrics.unattendedTaskRatio * 100).toFixed(1)}%`,
    )

    console.log(`🔧 Resource Utilization:`)
    const topWorkCells = Array.from(analytics.resourceMetrics.modesByWorkCell.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)

    topWorkCells.forEach(([workCell, count]) => {
      console.log(`   ${workCell}: ${count} task modes`)
    })

    console.log(`🧠 Skill Distribution:`)
    Array.from(analytics.resourceMetrics.modesBySkillLevel.entries()).forEach(([skill, count]) => {
      console.log(`   ${skill}: ${count} requirements`)
    })

    if (analytics.resourceMetrics.capacityBottlenecks.length > 0) {
      console.log(`⚠️ Capacity Bottlenecks:`)
      analytics.resourceMetrics.capacityBottlenecks.forEach((bottleneck) => {
        console.log(
          `   ${bottleneck.resource} (${bottleneck.type}): ${bottleneck.demandCount} demands`,
        )
      })
    }

    return analytics
  } catch (error) {
    console.error('❌ Analytics generation failed:', error)
    throw error
  }
}

/**
 * Example 6: Cache Management for Long-Running Operations
 * Demonstrate cache optimization for manufacturing batch processes
 */
export async function demonstrateCacheManagement() {
  const pipeline = getManufacturingDataPipeline()
  const dataService = pipeline.getDataService()

  try {
    console.log('🗄️ Demonstrating cache management...')

    // Simulate heavy data loading that benefits from caching
    const startTime = Date.now()

    // First load - cache miss
    console.log('Loading data (cache miss expected)...')
    const jobs1 = await dataService.loadJobsWithTasks({ limit: 100 })
    const time1 = Date.now() - startTime

    console.log(`✅ First load: ${time1}ms (${jobs1.jobs.length} jobs)`)

    // Second load - should benefit from value object caching
    const start2 = Date.now()
    const _jobs2 = await dataService.loadJobsWithTasks({ limit: 100 })
    const time2 = Date.now() - start2

    console.log(`✅ Second load: ${time2}ms (cached value objects)`)
    console.log(`🚀 Performance improvement: ${(((time1 - time2) / time1) * 100).toFixed(1)}%`)

    // Clear caches manually (usually done automatically)
    console.log('🧹 Clearing caches...')
    dataService.clearAllCaches()

    // Third load after cache clear
    const start3 = Date.now()
    const _jobs3 = await dataService.loadJobsWithTasks({ limit: 100 })
    const time3 = Date.now() - start3

    console.log(`✅ Post-clear load: ${time3}ms (cache rebuilt)`)

    return {
      loadTimes: { initial: time1, cached: time2, postClear: time3 },
      improvementPercent: ((time1 - time2) / time1) * 100,
    }
  } catch (error) {
    console.error('❌ Cache management demo failed:', error)
    throw error
  }
}

/**
 * Complete manufacturing data pipeline demonstration
 * Run all examples to show optimized data layer capabilities
 */
export async function runCompleteDemo() {
  console.log('🚀 Starting complete manufacturing data pipeline demonstration...\n')

  try {
    // Example 1: Dashboard loading
    await loadManufacturingDashboard()
    console.log('\n' + '='.repeat(60) + '\n')

    // Example 2: Scheduling data
    await loadSchedulingData()
    console.log('\n' + '='.repeat(60) + '\n')

    // Example 3: Bulk operations
    await processBulkJobOperations()
    console.log('\n' + '='.repeat(60) + '\n')

    // Example 4: Performance monitoring
    await monitorPerformance()
    console.log('\n' + '='.repeat(60) + '\n')

    // Example 5: Analytics
    await generateManufacturingAnalytics()
    console.log('\n' + '='.repeat(60) + '\n')

    // Example 6: Cache management
    await demonstrateCacheManagement()
    console.log('\n' + '='.repeat(60) + '\n')

    console.log('✅ Complete demonstration finished successfully!')

    // Final performance summary
    const pipeline = getManufacturingDataPipeline()
    const finalMetrics = pipeline.getPerformanceMonitor().getPerformanceMetrics()
    console.log(`\n📊 Final Performance Summary:`)
    console.log(`   Total operations: ${finalMetrics.queryMetrics.length}`)
    console.log(
      `   Average query time: ${finalMetrics.queryMetrics.reduce((sum, q) => sum + q.averageTime, 0) / finalMetrics.queryMetrics.length || 0}ms`,
    )
    console.log(`   Recommendations: ${finalMetrics.recommendations.length}`)
  } catch (error) {
    console.error('❌ Demo execution failed:', error)
    throw error
  }
}

// Export usage examples for Next.js pages or API routes
export const manufacturingDataExamples = {
  loadManufacturingDashboard,
  loadSchedulingData,
  processBulkJobOperations,
  monitorPerformance,
  generateManufacturingAnalytics,
  demonstrateCacheManagement,
  runCompleteDemo,
}
