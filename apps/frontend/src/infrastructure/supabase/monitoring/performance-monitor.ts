import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import { domainLogger } from '@/core/shared/logger'

/**
 * Performance monitoring utility for manufacturing data pipeline
 * Tracks query performance, connection usage, and optimization opportunities
 */
export class PerformanceMonitor {
  private queryMetrics: Map<
    string,
    {
      count: number
      totalTime: number
      averageTime: number
      lastExecuted: Date
    }
  > = new Map()

  private connectionMetrics = {
    activeConnections: 0,
    totalQueries: 0,
    slowQueries: 0,
    cacheHits: 0,
    cacheMisses: 0,
  }

  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Wrap a database operation with performance monitoring
   */
  async monitorQuery<T>(
    operation: string,
    queryFn: () => Promise<T>,
    options?: {
      logSlowQueries?: boolean
      slowQueryThreshold?: number
    },
  ): Promise<T> {
    const startTime = Date.now()
    const slowQueryThreshold = options?.slowQueryThreshold || 1000 // 1 second

    try {
      this.connectionMetrics.activeConnections++
      const result = await queryFn()

      const executionTime = Date.now() - startTime
      this.updateQueryMetrics(operation, executionTime)

      // Log slow queries for manufacturing optimization
      if (executionTime > slowQueryThreshold && options?.logSlowQueries) {
        domainLogger.infrastructure.warn(`Slow query detected: ${operation}`, {
          operation,
          executionTime,
          threshold: slowQueryThreshold,
        })
        this.connectionMetrics.slowQueries++
      }

      this.connectionMetrics.totalQueries++
      return result
    } catch (error) {
      domainLogger.infrastructure.error(`Query failed: ${operation}`, error as Error, {
        operation,
        executionTime: Date.now() - startTime,
      })
      throw error
    } finally {
      this.connectionMetrics.activeConnections--
    }
  }

  /**
   * Get performance metrics for manufacturing dashboard
   */
  getPerformanceMetrics(): {
    queryMetrics: Array<{
      operation: string
      count: number
      averageTime: number
      totalTime: number
      lastExecuted: string
    }>
    connectionMetrics: typeof this.connectionMetrics
    recommendations: string[]
  } {
    const queryMetricsArray = Array.from(this.queryMetrics.entries())
      .map(([operation, metrics]) => ({
        operation,
        count: metrics.count,
        averageTime: Math.round(metrics.averageTime),
        totalTime: metrics.totalTime,
        lastExecuted: metrics.lastExecuted.toISOString(),
      }))
      .sort((a, b) => b.averageTime - a.averageTime)

    const recommendations = this.generateRecommendations(queryMetricsArray)

    return {
      queryMetrics: queryMetricsArray,
      connectionMetrics: { ...this.connectionMetrics },
      recommendations,
    }
  }

  /**
   * Monitor database health for manufacturing workloads
   */
  async checkDatabaseHealth(): Promise<{
    status: 'healthy' | 'degraded' | 'critical'
    metrics: {
      connectionCount: number
      activeQueries: number
      avgQueryTime: number
      errorRate: number
    }
    issues: string[]
  }> {
    const issues: string[] = []
    let status: 'healthy' | 'degraded' | 'critical' = 'healthy'

    try {
      // Check connection pool status
      if (this.connectionMetrics.activeConnections > 15) {
        issues.push('High connection usage detected')
        status = 'degraded'
      }

      // Check query performance
      const recentQueries = Array.from(this.queryMetrics.values()).filter(
        (metric) => Date.now() - metric.lastExecuted.getTime() < 300000,
      ) // Last 5 minutes

      if (recentQueries.length > 0) {
        const avgQueryTime =
          recentQueries.reduce((sum, metric) => sum + metric.averageTime, 0) / recentQueries.length

        if (avgQueryTime > 2000) {
          issues.push(`High average query time: ${Math.round(avgQueryTime)}ms`)
          status = avgQueryTime > 5000 ? 'critical' : 'degraded'
        }
      }

      // Check slow query ratio
      const slowQueryRatio =
        this.connectionMetrics.totalQueries > 0
          ? this.connectionMetrics.slowQueries / this.connectionMetrics.totalQueries
          : 0

      if (slowQueryRatio > 0.1) {
        issues.push(`High slow query ratio: ${Math.round(slowQueryRatio * 100)}%`)
        status = 'degraded'
      }

      // Check cache efficiency
      const cacheTotal = this.connectionMetrics.cacheHits + this.connectionMetrics.cacheMisses
      const cacheHitRatio = cacheTotal > 0 ? this.connectionMetrics.cacheHits / cacheTotal : 0

      if (cacheHitRatio < 0.7 && cacheTotal > 100) {
        issues.push(`Low cache hit ratio: ${Math.round(cacheHitRatio * 100)}%`)
        status = 'degraded'
      }

      const healthMetrics = {
        connectionCount: this.connectionMetrics.activeConnections,
        activeQueries: recentQueries.length,
        avgQueryTime:
          recentQueries.length > 0
            ? Math.round(
                recentQueries.reduce((sum, m) => sum + m.averageTime, 0) / recentQueries.length,
              )
            : 0,
        errorRate: 0, // Would need error tracking implementation
      }

      domainLogger.infrastructure.info(`Database health check: ${status}`, {
        status,
        issues: issues.length,
        metrics: healthMetrics,
      })

      return {
        status,
        metrics: healthMetrics,
        issues,
      }
    } catch (error) {
      domainLogger.infrastructure.error('Database health check failed', error as Error)
      return {
        status: 'critical',
        metrics: { connectionCount: 0, activeQueries: 0, avgQueryTime: 0, errorRate: 1 },
        issues: ['Health check failed'],
      }
    }
  }

  /**
   * Reset metrics (useful for long-running manufacturing processes)
   */
  resetMetrics(): void {
    this.queryMetrics.clear()
    this.connectionMetrics = {
      activeConnections: 0,
      totalQueries: 0,
      slowQueries: 0,
      cacheHits: 0,
      cacheMisses: 0,
    }
    domainLogger.infrastructure.info('Performance metrics reset')
  }

  /**
   * Record cache hit/miss for optimization tracking
   */
  recordCacheHit(hit: boolean): void {
    if (hit) {
      this.connectionMetrics.cacheHits++
    } else {
      this.connectionMetrics.cacheMisses++
    }
  }

  /**
   * Get manufacturing-specific performance insights
   */
  getManufacturingInsights(): {
    batchOperationEfficiency: number
    recommendedBatchSize: number
    peakUsageHours: string[]
    optimizationOpportunities: Array<{
      type: 'index' | 'query' | 'cache' | 'batch'
      description: string
      impact: 'high' | 'medium' | 'low'
    }>
  } {
    const insights = {
      batchOperationEfficiency: this.calculateBatchEfficiency(),
      recommendedBatchSize: this.calculateOptimalBatchSize(),
      peakUsageHours: this.identifyPeakHours(),
      optimizationOpportunities: this.identifyOptimizations(),
    }

    domainLogger.infrastructure.info('Generated manufacturing insights', insights)
    return insights
  }

  private updateQueryMetrics(operation: string, executionTime: number): void {
    const existing = this.queryMetrics.get(operation)

    if (existing) {
      existing.count++
      existing.totalTime += executionTime
      existing.averageTime = existing.totalTime / existing.count
      existing.lastExecuted = new Date()
    } else {
      this.queryMetrics.set(operation, {
        count: 1,
        totalTime: executionTime,
        averageTime: executionTime,
        lastExecuted: new Date(),
      })
    }
  }

  private generateRecommendations(
    queryMetrics: Array<{
      operation: string
      averageTime: number
      count: number
    }>,
  ): string[] {
    const recommendations: string[] = []

    // Slow query recommendations
    const slowQueries = queryMetrics.filter((q) => q.averageTime > 1000)
    if (slowQueries.length > 0) {
      recommendations.push(`Consider optimizing ${slowQueries.length} slow queries`)
    }

    // Frequent query recommendations
    const frequentQueries = queryMetrics.filter((q) => q.count > 100)
    if (frequentQueries.length > 0) {
      recommendations.push(
        `Consider caching results for ${frequentQueries.length} frequent queries`,
      )
    }

    // Connection pool recommendations
    if (this.connectionMetrics.activeConnections > 10) {
      recommendations.push('Consider increasing connection pool size')
    }

    // Manufacturing-specific recommendations
    const jobQueries = queryMetrics.filter((q) => q.operation.includes('job'))
    const taskQueries = queryMetrics.filter((q) => q.operation.includes('task'))

    if (jobQueries.length > taskQueries.length * 2) {
      recommendations.push('Consider batch loading tasks with jobs to reduce N+1 queries')
    }

    return recommendations
  }

  private calculateBatchEfficiency(): number {
    const batchQueries = Array.from(this.queryMetrics.entries()).filter(
      ([operation]) => operation.includes('batch') || operation.includes('bulk'),
    )

    if (batchQueries.length === 0) return 0

    const avgBatchTime =
      batchQueries.reduce((sum, [, metrics]) => sum + metrics.averageTime, 0) / batchQueries.length
    const avgSingleTime = 100 // Assume average single query time

    return Math.max(
      0,
      Math.min(100, ((avgSingleTime * 10 - avgBatchTime) / (avgSingleTime * 10)) * 100),
    )
  }

  private calculateOptimalBatchSize(): number {
    // Based on query performance patterns, recommend batch size
    const avgQueryTime =
      Array.from(this.queryMetrics.values()).reduce(
        (sum, metrics) => sum + metrics.averageTime,
        0,
      ) / this.queryMetrics.size

    if (avgQueryTime < 100) return 1000 // Fast queries can handle larger batches
    if (avgQueryTime < 500) return 500 // Medium speed
    return 200 // Slow queries need smaller batches
  }

  private identifyPeakHours(): string[] {
    // Analyze query timestamps to identify peak usage hours
    // Simplified implementation - would need more sophisticated analysis
    const currentHour = new Date().getHours()
    return [`${currentHour}:00-${currentHour + 1}:00`]
  }

  private identifyOptimizations(): Array<{
    type: 'index' | 'query' | 'cache' | 'batch'
    description: string
    impact: 'high' | 'medium' | 'low'
  }> {
    const optimizations: Array<{
      type: 'index' | 'query' | 'cache' | 'batch'
      description: string
      impact: 'high' | 'medium' | 'low'
    }> = []

    // Analyze query patterns for optimization opportunities
    const slowQueries = Array.from(this.queryMetrics.entries()).filter(
      ([, metrics]) => metrics.averageTime > 1000,
    )

    if (slowQueries.length > 0) {
      optimizations.push({
        type: 'index',
        description: 'Add database indexes for slow queries',
        impact: 'high',
      })
    }

    const cacheTotal = this.connectionMetrics.cacheHits + this.connectionMetrics.cacheMisses
    const cacheHitRatio = cacheTotal > 0 ? this.connectionMetrics.cacheHits / cacheTotal : 1

    if (cacheHitRatio < 0.8) {
      optimizations.push({
        type: 'cache',
        description: 'Implement caching for frequently accessed data',
        impact: 'medium',
      })
    }

    const batchQueries = Array.from(this.queryMetrics.keys()).filter(
      (op) => op.includes('batch') || op.includes('bulk'),
    )

    if (batchQueries.length < 5) {
      optimizations.push({
        type: 'batch',
        description: 'Implement more batch operations for manufacturing workflows',
        impact: 'high',
      })
    }

    return optimizations
  }
}

/**
 * Singleton instance for global performance monitoring
 */
let performanceMonitorInstance: PerformanceMonitor | null = null

export function getPerformanceMonitor(supabase: SupabaseClient<Database>): PerformanceMonitor {
  if (!performanceMonitorInstance) {
    performanceMonitorInstance = new PerformanceMonitor(supabase)
  }
  return performanceMonitorInstance
}
