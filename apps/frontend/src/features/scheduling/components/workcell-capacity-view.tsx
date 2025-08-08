'use client'

import dynamic from 'next/dynamic'
import { Skeleton } from '@/shared/ui/skeleton'

const WorkCellCapacityViewInner = dynamic(
  () => import('./workcell-capacity-view.inner').then(m => m.WorkCellCapacityViewInner),
  { ssr: false, loading: () => <Skeleton className="h-[600px] w-full" /> }
)

export { type WorkCellCapacityViewProps } from './workcell-capacity-view.inner'

export function WorkCellCapacityView(
  props: import('./workcell-capacity-view.inner').WorkCellCapacityViewProps,
) {
  return <WorkCellCapacityViewInner {...props} />
}
  className,
  onWorkCellClick,
  onTaskClick,
}: WorkCellCapacityViewProps) {
  const [workCells, setWorkCells] = useState<WorkCellCapacity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [_selectedMetric, _setSelectedMetric] = useState<'utilization' | 'efficiency' | 'tasks'>(
    'utilization',
  )
  const [viewMode, setViewMode] = useState<'cards' | 'timeline' | 'chart'>('cards')

  // Load and update data
  useEffect(() => {
    const loadData = () => {
      setIsLoading(true)
      setTimeout(() => {
        const allWorkCells = generateMockWorkCells()
        const filtered = allWorkCells.filter((wc) => {
          if (workCellIds && !workCellIds.includes(wc.id)) return false
          if (department && wc.department !== department) return false
          return true
        })
        setWorkCells(filtered)
        setIsLoading(false)
      }, 1000)
    }

    loadData()

    // Real-time updates
    if (enableRealtime) {
      const interval = setInterval(() => {
        setWorkCells((prev) =>
          prev.map((wc) => ({
            ...wc,
            utilization: Math.max(0, Math.min(100, wc.utilization + (Math.random() - 0.5) * 10)),
            efficiency: Math.max(60, Math.min(100, wc.efficiency + (Math.random() - 0.5) * 5)),
            lastUpdate: new Date(),
            // Simulate task completion and new tasks
            currentTasks: wc.currentTasks.filter(
              (task) => Math.random() > 0.1 || task.endTime > new Date(),
            ),
          })),
        )
      }, 5000) // Update every 5 seconds

      return () => clearInterval(interval)
    }
  }, [workCellIds, department, enableRealtime])

  // Calculate time slots for timeline view
  const timeSlots = useMemo(() => {
    const slots = []
    const now = new Date()
    const hours =
      timeHorizon === '4h'
        ? 4
        : timeHorizon === '8h'
          ? 8
          : timeHorizon === '24h'
            ? 24
            : timeHorizon === '3d'
              ? 72
              : 168

    for (let i = 0; i < hours; i++) {
      const time = new Date(now.getTime() + i * 60 * 60 * 1000)
      slots.push({
        time,
        hour: time.getHours(),
        label:
          timeHorizon === '4h' || timeHorizon === '8h'
            ? time.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true })
            : `${time.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${time.getHours()}:00`,
      })
    }

    return slots
  }, [timeHorizon])

  // Calculate capacity forecast for each time slot
  const getCapacityForecast = useCallback((workCell: WorkCellCapacity, slotTime: Date) => {
    const slotEnd = new Date(slotTime.getTime() + 60 * 60 * 1000) // 1 hour slot

    const activeTasks = [
      ...workCell.currentTasks.filter(
        (task) => task.endTime > slotTime && task.startTime < slotEnd,
      ),
      ...workCell.scheduledTasks.filter(
        (task) => task.startTime < slotEnd && task.endTime > slotTime,
      ),
    ]

    const totalCapacityUsed = activeTasks.reduce((sum, task) => sum + task.requiredCapacity, 0)
    const taskCount = activeTasks.length
    const utilization = Math.min((totalCapacityUsed / workCell.maxCapacityUnits) * 100, 100)
    const taskLoad = Math.min((taskCount / workCell.maxConcurrentTasks) * 100, 100)

    return {
      utilization,
      taskLoad,
      taskCount,
      capacityUsed: totalCapacityUsed,
      tasks: activeTasks,
      isOverloaded:
        taskCount > workCell.maxConcurrentTasks || totalCapacityUsed > workCell.maxCapacityUnits,
    }
  }, [])

  // Summary metrics
  const summaryMetrics = useMemo(() => {
    if (workCells.length === 0)
      return { avgUtilization: 0, avgEfficiency: 0, bottleneckCount: 0, totalTasks: 0 }

    const avgUtilization = workCells.reduce((sum, wc) => sum + wc.utilization, 0) / workCells.length
    const avgEfficiency = workCells.reduce((sum, wc) => sum + wc.efficiency, 0) / workCells.length
    const bottleneckCount = workCells.filter(
      (wc) => wc.utilization > 90 || wc.status === 'reduced_capacity',
    ).length
    const totalTasks = workCells.reduce((sum, wc) => sum + wc.currentTasks.length, 0)

    return { avgUtilization, avgEfficiency, bottleneckCount, totalTasks }
  }, [workCells])

  const renderCardsView = () => (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
      {workCells.map((workCell) => {
        const isBottleneck = workCell.utilization > 90
        const upcomingTasks = workCell.scheduledTasks.filter(
          (task) => task.startTime.getTime() - Date.now() < 4 * 60 * 60 * 1000, // Next 4 hours
        )

        return (
          <Card
            key={workCell.id}
            className={cn(
              'cursor-pointer transition-shadow hover:shadow-md',
              isBottleneck && 'ring-2 ring-orange-200',
            )}
            onClick={() => onWorkCellClick?.(workCell)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <CardTitle className="truncate text-lg">{workCell.name}</CardTitle>
                  <CardDescription>{workCell.department}</CardDescription>
                </div>
                <div className="flex flex-col items-end space-y-2">
                  <Badge className={STATUS_COLORS[workCell.status]}>
                    {workCell.status.replace('_', ' ')}
                  </Badge>
                  {isBottleneck && (
                    <Badge variant="destructive" className="text-xs">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      Bottleneck
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Capacity meters */}
              <div className="space-y-3">
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">Capacity Utilization</span>
                    <span className="text-sm text-gray-600">
                      {workCell.utilization.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={cn(
                        'h-full transition-all duration-300',
                        workCell.utilization > 90
                          ? 'bg-red-500'
                          : workCell.utilization > 70
                            ? 'bg-yellow-500'
                            : 'bg-green-500',
                      )}
                      style={{ width: `${Math.min(workCell.utilization, 100)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">Task Load</span>
                    <span className="text-sm text-gray-600">
                      {workCell.currentTasks.length}/{workCell.maxConcurrentTasks}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={cn(
                        'h-full transition-all duration-300',
                        workCell.currentTasks.length >= workCell.maxConcurrentTasks
                          ? 'bg-red-500'
                          : workCell.currentTasks.length / workCell.maxConcurrentTasks > 0.7
                            ? 'bg-yellow-500'
                            : 'bg-blue-500',
                      )}
                      style={{
                        width: `${Math.min((workCell.currentTasks.length / workCell.maxConcurrentTasks) * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">Efficiency</span>
                    <span className="text-sm text-gray-600">{workCell.efficiency}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className="h-full bg-purple-500 transition-all duration-300"
                      style={{ width: `${workCell.efficiency}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Current tasks */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-medium">Current Tasks</h4>
                  <Activity className="h-4 w-4 text-gray-400" />
                </div>
                {workCell.currentTasks.length === 0 ? (
                  <p className="text-sm text-gray-500">No active tasks</p>
                ) : (
                  <div className="max-h-24 space-y-1 overflow-y-auto">
                    {workCell.currentTasks.slice(0, 3).map((task) => (
                      <div
                        key={task.taskId}
                        className={cn(
                          'cursor-pointer rounded border-l-2 p-2 text-xs hover:bg-gray-50',
                          PRIORITY_INDICATORS[task.priority],
                        )}
                        onClick={(e) => {
                          e.stopPropagation()
                          onTaskClick?.(task)
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="truncate font-medium">{task.taskName}</span>
                          <Badge
                            variant="outline"
                            className={cn('text-xs', TASK_STATUS_COLORS[task.status])}
                          >
                            {task.status}
                          </Badge>
                        </div>
                        <div className="mt-1 text-gray-500">
                          Ends: {task.endTime.toLocaleTimeString()}
                        </div>
                      </div>
                    ))}
                    {workCell.currentTasks.length > 3 && (
                      <div className="text-center text-xs text-gray-500">
                        +{workCell.currentTasks.length - 3} more tasks
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Upcoming tasks forecast */}
              {showForecast && upcomingTasks.length > 0 && (
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-medium">Next 4 Hours</h4>
                    <Clock className="h-4 w-4 text-gray-400" />
                  </div>
                  <div className="text-xs text-gray-600">
                    {upcomingTasks.length} task{upcomingTasks.length !== 1 ? 's' : ''} scheduled
                    {upcomingTasks.some((t) => t.priority === 'critical') && (
                      <Badge variant="destructive" className="ml-2 text-xs">
                        Critical
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Last update */}
              <div className="border-t pt-2 text-xs text-gray-500">
                Updated: {workCell.lastUpdate.toLocaleTimeString()}
                {enableRealtime && (
                  <div className="mt-1 flex items-center">
                    <div className="mr-1 h-2 w-2 animate-pulse rounded-full bg-green-500" />
                    Live updates
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )

  const renderTimelineView = () => (
    <div className="space-y-4">
      {workCells.map((workCell) => (
        <Card key={workCell.id}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">{workCell.name}</CardTitle>
                <CardDescription>
                  {workCell.department} • Max: {workCell.maxConcurrentTasks} tasks,{' '}
                  {workCell.maxCapacityUnits} units
                </CardDescription>
              </div>
              <Badge className={STATUS_COLORS[workCell.status]}>
                {workCell.status.replace('_', ' ')}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <div className="min-w-full">
                {/* Timeline header */}
                <div className="mb-2 flex">
                  <div className="w-24 py-1 text-xs font-medium text-gray-600">Capacity</div>
                  {timeSlots.map((slot, index) => (
                    <div
                      key={index}
                      className="w-16 border-l py-1 text-center text-xs text-gray-600"
                    >
                      {slot.label}
                    </div>
                  ))}
                </div>

                {/* Capacity bars */}
                <div className="flex">
                  <div className="w-24 py-2 text-xs text-gray-600">Load</div>
                  {timeSlots.map((slot, index) => {
                    const forecast = getCapacityForecast(workCell, slot.time)

                    return (
                      <div key={index} className="w-16 border-l p-1">
                        <div className="relative h-12 rounded bg-gray-100">
                          {/* Task load */}
                          <div
                            className={cn(
                              'absolute bottom-0 left-0 right-0 rounded transition-all',
                              forecast.isOverloaded
                                ? 'bg-red-500'
                                : forecast.taskLoad > 70
                                  ? 'bg-yellow-500'
                                  : 'bg-green-500',
                            )}
                            style={{ height: `${Math.min(forecast.taskLoad, 100)}%` }}
                          />

                          {/* Capacity utilization overlay */}
                          <div
                            className="absolute bottom-0 left-0 w-1 rounded-l bg-blue-500"
                            style={{ height: `${Math.min(forecast.utilization, 100)}%` }}
                          />

                          {forecast.isOverloaded && (
                            <AlertTriangle className="absolute right-0 top-0 h-3 w-3 text-red-600" />
                          )}
                        </div>

                        <div className="mt-1 text-center text-xs">{forecast.taskCount}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Factory className="mr-2 h-5 w-5" />
            WorkCell Capacity
          </CardTitle>
          <CardDescription>Loading capacity data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (workCells.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Factory className="mr-2 h-5 w-5" />
            WorkCell Capacity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="py-8 text-center">
            <Factory className="mx-auto mb-4 h-12 w-12 text-gray-300" />
            <h3 className="mb-2 text-lg font-medium">No WorkCells Found</h3>
            <p className="text-sm text-gray-500">No workcells match the selected filters.</p>
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
              <Factory className="mr-2 h-5 w-5" />
              WorkCell Capacity
            </CardTitle>
            <CardDescription>
              {workCells.length} workcell{workCells.length !== 1 ? 's' : ''} •{' '}
              {summaryMetrics.totalTasks} active tasks
              {summaryMetrics.bottleneckCount > 0 && (
                <span className="ml-2 text-orange-600">
                  • {summaryMetrics.bottleneckCount} bottleneck
                  {summaryMetrics.bottleneckCount !== 1 ? 's' : ''}
                </span>
              )}
            </CardDescription>
          </div>

          <div className="flex items-center space-x-2">
            	<Select
              value={viewMode}
              onValueChange={(value) => setViewMode(value as 'cards' | 'timeline' | 'chart')}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cards">Cards</SelectItem>
                <SelectItem value="timeline">Timeline</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={timeHorizon}
              onValueChange={() => {
                /* Time horizon change */
              }}
            >
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="4h">4h</SelectItem>
                <SelectItem value="8h">8h</SelectItem>
                <SelectItem value="24h">24h</SelectItem>
                <SelectItem value="3d">3d</SelectItem>
                <SelectItem value="1w">1w</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Summary metrics */}
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded bg-blue-50 p-3 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {summaryMetrics.avgUtilization.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Avg Utilization</div>
          </div>
          <div className="rounded bg-green-50 p-3 text-center">
            <div className="text-2xl font-bold text-green-600">
              {summaryMetrics.avgEfficiency.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Avg Efficiency</div>
          </div>
          <div className="rounded bg-purple-50 p-3 text-center">
            <div className="text-2xl font-bold text-purple-600">{summaryMetrics.totalTasks}</div>
            <div className="text-sm text-gray-600">Active Tasks</div>
          </div>
          <div className="rounded bg-orange-50 p-3 text-center">
            <div
              className={cn(
                'text-2xl font-bold',
                summaryMetrics.bottleneckCount > 0 ? 'text-orange-600' : 'text-green-600',
              )}
            >
              {summaryMetrics.bottleneckCount}
            </div>
            <div className="text-sm text-gray-600">Bottlenecks</div>
          </div>
        </div>

        {/* Bottleneck alert */}
        {summaryMetrics.bottleneckCount > 0 && (
          <Alert className="mt-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {summaryMetrics.bottleneckCount} workcell
              {summaryMetrics.bottleneckCount !== 1 ? 's' : ''} operating at high capacity. Consider
              load balancing or increasing capacity.
            </AlertDescription>
          </Alert>
        )}
      </CardHeader>

      <CardContent>
        <div style={{ height: `${height}px` }} className="overflow-y-auto">
          {viewMode === 'timeline' ? renderTimelineView() : renderCardsView()}
        </div>

        {/* Footer */}
        <div className="mt-4 border-t pt-4 text-xs text-gray-600">
          <div className="flex items-center justify-between">
            <div>Last updated: {new Date().toLocaleTimeString()}</div>
            <div className="flex items-center space-x-4">
              {enableRealtime && (
                <span className="flex items-center text-green-600">
                  <div className="mr-1 h-2 w-2 animate-pulse rounded-full bg-green-500" />
                  Real-time monitoring
                </span>
              )}
              <span>Target efficiency: 85%</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
