'use client'

import dynamic from 'next/dynamic'
import { Skeleton } from '@/shared/ui/skeleton'

// Thin shell that lazy-loads the heavy implementation on the client only
const ResourceUtilizationChartInner = dynamic(
  () => import('./resource-utilization-chart.inner').then(m => m.ResourceUtilizationChartInner),
  { ssr: false, loading: () => <Skeleton className="h-80 w-full" /> }
)

export { type ResourceUtilizationChartProps } from './resource-utilization-chart.inner'

export function ResourceUtilizationChart(
  props: import('./resource-utilization-chart.inner').ResourceUtilizationChartProps,
) {
  return <ResourceUtilizationChartInner {...props} />
}

  // Filter resources based on props
  const filteredResources = useMemo(() => {
    return resources.filter((resource) => {
      if (resourceType !== 'all' && resource.type !== resourceType) return false
      if (department && resource.department !== department) return false
      return true
    })
  }, [resources, resourceType, department])

  // Calculate summary metrics
  const summaryMetrics = useMemo(() => {
    if (filteredResources.length === 0) {
      return { avgUtilization: 0, avgEfficiency: 0, avgAvailability: 0, activeCount: 0 }
    }

    const avgUtilization =
      filteredResources.reduce((sum, r) => sum + (r.current / r.capacity) * 100, 0) /
      filteredResources.length
    const avgEfficiency =
      filteredResources.reduce((sum, r) => sum + r.efficiency, 0) / filteredResources.length
    const avgAvailability =
      filteredResources.reduce((sum, r) => sum + r.availability, 0) / filteredResources.length
    const activeCount = filteredResources.filter((r) => r.status === 'active').length

    return { avgUtilization, avgEfficiency, avgAvailability, activeCount }
  }, [filteredResources])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setResources(generateMockResourceData())
      setIsRefreshing(false)
    }, 1000)
  }, [])

  const getMetricValue = useCallback((resource: ResourceData, metric: string) => {
    switch (metric) {
      case 'utilization':
        return (resource.current / resource.capacity) * 100
      case 'efficiency':
        return resource.efficiency
      case 'availability':
        return resource.availability
      default:
        return 0
    }
  }, [])

  const getMetricTarget = useCallback((resourceType: string) => {
    return UTILIZATION_TARGETS[resourceType as keyof typeof UTILIZATION_TARGETS] || 80
  }, [])

  const renderBarChart = () => {
    const maxValue = Math.max(
      ...filteredResources.map((r) => getMetricValue(r, selectedMetric)),
      100,
    )

    return (
      <div className="space-y-3">
        {filteredResources.map((resource) => {
          const value = getMetricValue(resource, selectedMetric)
          const target = getMetricTarget(resource.type)
          const percentage = (value / maxValue) * 100
          const isAboveTarget = value >= target

          return (
            <div key={resource.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex min-w-0 items-center space-x-2">
                  <span className="truncate text-sm font-medium">{resource.name}</span>
                  <Badge variant="outline" className={STATUS_COLORS[resource.status]}>
                    {resource.status}
                  </Badge>
                </div>
                <div className="flex items-center space-x-2 text-sm">
                  <span
                    className={cn('font-medium', isAboveTarget ? 'text-green-600' : 'text-red-600')}
                  >
                    {value.toFixed(1)}%
                  </span>
                  {showTargets && <span className="text-gray-500">/ {target}%</span>}
                </div>
              </div>

              <div className="relative">
                <div className="h-6 overflow-hidden rounded-full bg-gray-200">
                  <div
                    className={cn(
                      'h-full transition-all duration-300',
                      isAboveTarget ? 'bg-green-500' : 'bg-red-500',
                    )}
                    style={{ width: `${Math.min(percentage, 100)}%` }}
                  />
                  {showTargets && (
                    <div
                      className="absolute bottom-0 top-0 w-0.5 bg-gray-600"
                      style={{ left: `${(target / maxValue) * 100}%` }}
                    />
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const renderDonutChart = () => {
    const statusCounts = filteredResources.reduce(
      (acc, resource) => {
        acc[resource.status] = (acc[resource.status] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )

    const total = filteredResources.length
    const colors = ['#10b981', '#f59e0b', '#f97316', '#ef4444'] // green, yellow, orange, red

    let currentAngle = 0
    const segments = Object.entries(statusCounts).map(([status, count], index) => {
      const percentage = (count / total) * 100
      const angle = (count / total) * 360
      const startAngle = currentAngle
      const endAngle = currentAngle + angle
      currentAngle = endAngle

      // Calculate path for SVG arc
      const centerX = 100
      const centerY = 100
      const radius = 80
      const innerRadius = 40

      const startAngleRad = ((startAngle - 90) * Math.PI) / 180
      const endAngleRad = ((endAngle - 90) * Math.PI) / 180

      const x1 = centerX + radius * Math.cos(startAngleRad)
      const y1 = centerY + radius * Math.sin(startAngleRad)
      const x2 = centerX + radius * Math.cos(endAngleRad)
      const y2 = centerY + radius * Math.sin(endAngleRad)

      const x3 = centerX + innerRadius * Math.cos(endAngleRad)
      const y3 = centerY + innerRadius * Math.sin(endAngleRad)
      const x4 = centerX + innerRadius * Math.cos(startAngleRad)
      const y4 = centerY + innerRadius * Math.sin(startAngleRad)

      const largeArcFlag = angle > 180 ? 1 : 0

      const pathData = [
        `M ${x1} ${y1}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
        `L ${x3} ${y3}`,
        `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x4} ${y4}`,
        'Z',
      ].join(' ')

      return {
        status,
        count,
        percentage,
        pathData,
        color: colors[index % colors.length],
      }
    })

    return (
      <div className="flex items-center justify-center space-x-8">
        <svg width="200" height="200" className="flex-shrink-0">
          {segments.map((segment) => (
            <path
              key={segment.status}
              d={segment.pathData}
              fill={segment.color}
              className="cursor-pointer hover:opacity-80"
              onClick={() => {
                // Filter by status functionality could be added here
              }}
            />
          ))}
          <text x="100" y="95" textAnchor="middle" className="text-lg font-bold">
            {total}
          </text>
          <text x="100" y="110" textAnchor="middle" className="text-sm text-gray-600">
            Resources
          </text>
        </svg>

        <div className="space-y-2">
          {segments.map((segment) => (
            <div key={segment.status} className="flex items-center space-x-2">
              <div className="h-4 w-4 rounded" style={{ backgroundColor: segment.color }} />
              <span className="text-sm capitalize">{segment.status}</span>
              <span className="text-sm text-gray-500">
                {segment.count} ({segment.percentage.toFixed(1)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Activity className="mr-2 h-5 w-5" />
            Resource Utilization
          </CardTitle>
          <CardDescription>Loading resource data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-6 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (filteredResources.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Activity className="mr-2 h-5 w-5" />
            Resource Utilization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="py-8 text-center">
            <Activity className="mx-auto mb-4 h-12 w-12 text-gray-300" />
            <h3 className="mb-2 text-lg font-medium">No Resources Found</h3>
            <p className="text-sm text-gray-500">No resources match the selected filters.</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center">
              <Activity className="mr-2 h-5 w-5" />
              Resource Utilization
            </CardTitle>
            <CardDescription>
              {filteredResources.length} resource{filteredResources.length !== 1 ? 's' : ''}{' '}
              monitored
              {enableRealtime && <span className="ml-2 text-green-600">• Live updates</span>}
            </CardDescription>
          </div>

          <div className="flex items-center space-x-2">
            	<Select
              value={selectedMetric}
              onValueChange={(value) =>
                setSelectedMetric(value as 'utilization' | 'efficiency' | 'availability')
              }
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="utilization">Utilization</SelectItem>
                <SelectItem value="efficiency">Efficiency</SelectItem>
                <SelectItem value="availability">Availability</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={chartType}
              onValueChange={() => {
                /* Chart type change handler */
              }}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="bar">Bar</SelectItem>
                <SelectItem value="donut">Donut</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
              <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
            </Button>
          </div>
        </div>

        {/* Summary metrics */}
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {summaryMetrics.avgUtilization.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Avg Utilization</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {summaryMetrics.avgEfficiency.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Avg Efficiency</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {summaryMetrics.avgAvailability.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Avg Availability</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">{summaryMetrics.activeCount}</div>
            <div className="text-sm text-gray-600">Active Resources</div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div style={{ height: `${height}px` }} className="overflow-y-auto">
          {chartType === 'donut' ? renderDonutChart() : renderBarChart()}
        </div>

        {/* Footer info */}
        <div className="mt-4 border-t pt-4 text-xs text-gray-600">
          <div className="flex items-center justify-between">
            <div>Last updated: {new Date().toLocaleTimeString()}</div>
            <div className="flex items-center space-x-4">
              {showTargets && (
                <span className="flex items-center">
                  <Target className="mr-1 h-3 w-3" />
                  Targets enabled
                </span>
              )}
              {enableRealtime && (
                <span className="flex items-center text-green-600">
                  <div className="mr-1 h-2 w-2 animate-pulse rounded-full bg-green-500" />
                  Real-time
                </span>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
