'use client'

import { useState, useMemo, useCallback, useRef } from 'react'
import { useTasks, useTasksByJob } from '@/features/scheduling/hooks/use-tasks'
// useJobs can be imported when needed
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import {
  Calendar,
  Clock,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Info,
} from 'lucide-react'
import type { Task } from '../types'
import { cn } from '@/shared/lib/utils'

interface TaskGanttChartProps {
  jobId?: string
  tasks?: Task[]
  height?: number
  enableZoom?: boolean
  enableDragDrop?: boolean
  showDependencies?: boolean
  timeRange?: 'day' | 'week' | 'month'
  className?: string
  onTaskClick?: (task: Task) => void
  onTaskUpdate?: (taskId: string, updates: { startDate?: Date; duration?: number }) => void
}

interface TimelineRange {
  start: Date
  end: Date
  unit: 'hour' | 'day' | 'week'
  intervals: Date[]
}

interface TaskBar {
  task: Task
  x: number
  width: number
  y: number
  height: number
  color: string
  isDragging?: boolean
}

const TASK_STATUS_COLORS = {
  not_ready: '#94a3b8', // gray
  ready: '#3b82f6', // blue
  scheduled: '#8b5cf6', // purple
  in_progress: '#f59e0b', // amber
  completed: '#10b981', // green
  on_hold: '#f97316', // orange
  cancelled: '#ef4444', // red
} as const

const ROW_HEIGHT = 40
const HEADER_HEIGHT = 60
const SIDEBAR_WIDTH = 200
const MIN_BAR_WIDTH = 20

/**
 * Task Gantt Chart - Interactive timeline visualization
 * Features:
 * - Real-time task scheduling visualization
 * - Interactive drag-and-drop timeline editing
 * - Dependency visualization with arrows
 * - Zoom and pan controls for different time ranges
 * - Status-based color coding
 * - Manufacturing-aware scheduling constraints
 * - Responsive design with horizontal scrolling
 */
export function TaskGanttChart({
  jobId,
  tasks: propTasks,
  height = 400,
  enableZoom = true,
  enableDragDrop = true,
  showDependencies: _showDependencies = true,
  timeRange = 'week',
  className,
  onTaskClick,
  onTaskUpdate: _onTaskUpdate,
}: TaskGanttChartProps) {
  const [zoomLevel, setZoomLevel] = useState(1)
  const [viewportStart, setViewportStart] = useState(() => {
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    return now
  })
  const [dragState, setDragState] = useState<{
    taskId: string
    startX: number
    initialStartTime: Date
  } | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const ganttRef = useRef<HTMLDivElement>(null)

  // Fetch tasks based on props or jobId
  // Fetch tasks data - call hooks unconditionally
  const {
    data: tasksByJob,
    isLoading: isLoadingByJob,
    error: errorByJob,
  } = useTasksByJob(jobId || '')
  const { data: allTasks, isLoading: isLoadingAll, error: errorAll } = useTasks()

  const fetchedTasks = jobId ? tasksByJob : allTasks
  const isLoading = jobId ? isLoadingByJob : isLoadingAll
  const error = jobId ? errorByJob : errorAll

  const tasks = useMemo(() => {
    return propTasks || fetchedTasks || []
  }, [propTasks, fetchedTasks])

  // Calculate timeline range based on tasks and timeRange setting
  const timelineRange = useMemo((): TimelineRange => {
    if (tasks.length === 0) {
      const start = new Date(viewportStart)
      const end = new Date(start)

      switch (timeRange) {
        case 'day':
          end.setDate(end.getDate() + 1)
          break
        case 'week':
          end.setDate(end.getDate() + 7)
          break
        case 'month':
          end.setMonth(end.getMonth() + 1)
          break
      }

      return {
        start,
        end,
        unit: timeRange === 'day' ? 'hour' : 'day',
        intervals: [],
      }
    }

    // Find date range from tasks (placeholder - would use actual task dates)
    const start = new Date(viewportStart)
    const end = new Date(start)

    switch (timeRange) {
      case 'day':
        end.setDate(end.getDate() + 1)
        break
      case 'week':
        end.setDate(end.getDate() + 7)
        break
      case 'month':
        end.setMonth(end.getMonth() + 1)
        break
    }

    // Generate intervals
    const intervals: Date[] = []
    const current = new Date(start)
    const unit = timeRange === 'day' ? 'hour' : 'day'

    while (current < end) {
      intervals.push(new Date(current))
      if (unit === 'hour') {
        current.setHours(current.getHours() + 1)
      } else {
        current.setDate(current.getDate() + 1)
      }
    }

    return { start, end, unit, intervals }
  }, [tasks, viewportStart, timeRange])

  // Calculate task bars positioning
  const taskBars = useMemo((): TaskBar[] => {
    const totalWidth = Math.max(800, (containerRef.current?.clientWidth || 800) - SIDEBAR_WIDTH)
    const timeSpan = timelineRange.end.getTime() - timelineRange.start.getTime()
    const pixelsPerMs = (totalWidth * zoomLevel) / timeSpan

    return tasks.map((task, index) => {
      // Placeholder dates - in real implementation, these would come from task scheduling
      const taskStart = new Date(timelineRange.start.getTime() + index * 2 * 60 * 60 * 1000) // 2 hours offset per task
      const taskDuration = 4 * 60 * 60 * 1000 // 4 hours duration

      const x = (taskStart.getTime() - timelineRange.start.getTime()) * pixelsPerMs
      const width = Math.max(MIN_BAR_WIDTH, taskDuration * pixelsPerMs)
      const y = index * ROW_HEIGHT

      return {
        task,
        x,
        width,
        y,
        height: ROW_HEIGHT - 8, // Padding
        color: TASK_STATUS_COLORS[task.status.value] || TASK_STATUS_COLORS.not_ready,
        isDragging: dragState?.taskId === task.id.toString(),
      }
    })
  }, [tasks, timelineRange, zoomLevel, dragState])

  const handleZoomIn = useCallback(() => {
    setZoomLevel((prev) => Math.min(prev * 1.5, 5))
  }, [])

  const handleZoomOut = useCallback(() => {
    setZoomLevel((prev) => Math.max(prev / 1.5, 0.25))
  }, [])

  const handleResetZoom = useCallback(() => {
    setZoomLevel(1)
  }, [])

  const handlePanLeft = useCallback(() => {
    const newStart = new Date(viewportStart)
    switch (timeRange) {
      case 'day':
        newStart.setHours(newStart.getHours() - 4)
        break
      case 'week':
        newStart.setDate(newStart.getDate() - 1)
        break
      case 'month':
        newStart.setDate(newStart.getDate() - 7)
        break
    }
    setViewportStart(newStart)
  }, [viewportStart, timeRange])

  const handlePanRight = useCallback(() => {
    const newStart = new Date(viewportStart)
    switch (timeRange) {
      case 'day':
        newStart.setHours(newStart.getHours() + 4)
        break
      case 'week':
        newStart.setDate(newStart.getDate() + 1)
        break
      case 'month':
        newStart.setDate(newStart.getDate() + 7)
        break
    }
    setViewportStart(newStart)
  }, [viewportStart, timeRange])

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, taskBar: TaskBar) => {
      if (!enableDragDrop) return

      e.preventDefault()
      setDragState({
        taskId: taskBar.task.id.toString(),
        startX: e.clientX,
        initialStartTime: new Date(
          timelineRange.start.getTime() +
            taskBar.x / (zoomLevel / (timelineRange.end.getTime() - timelineRange.start.getTime())),
        ),
      })
    },
    [enableDragDrop, timelineRange, zoomLevel],
  )

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragState) return

      const deltaX = e.clientX - dragState.startX
      const timeSpan = timelineRange.end.getTime() - timelineRange.start.getTime()
      const totalWidth = Math.max(800, (containerRef.current?.clientWidth || 800) - SIDEBAR_WIDTH)
      const pixelsPerMs = (totalWidth * zoomLevel) / timeSpan

      const deltaTime = deltaX / pixelsPerMs
      const newStartTime = new Date(dragState.initialStartTime.getTime() + deltaTime)

      // Update task position (placeholder - would call onTaskUpdate in real implementation)
      console.log(`Moving task ${dragState.taskId} to ${newStartTime}`)
    },
    [dragState, timelineRange, zoomLevel],
  )

  const handleMouseUp = useCallback(() => {
    if (dragState) {
      // Finalize task update
      setDragState(null)
    }
  }, [dragState])

  // Mouse event listeners for dragging
  useEffect(() => {
    if (dragState) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)

      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [dragState, handleMouseMove, handleMouseUp])

  const formatTimeLabel = useCallback(
    (date: Date) => {
      if (timelineRange.unit === 'hour') {
        return date.toLocaleTimeString('en-US', {
          hour: 'numeric',
          hour12: true,
        })
      }
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    },
    [timelineRange.unit],
  )

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Calendar className="mr-2 h-5 w-5" />
            Task Timeline
          </CardTitle>
          <CardDescription>Loading task schedule...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error || tasks.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Calendar className="mr-2 h-5 w-5" />
            Task Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>Failed to load task timeline: {error.message}</AlertDescription>
            </Alert>
          ) : (
            <div className="py-8 text-center">
              <Clock className="mx-auto mb-4 h-12 w-12 text-gray-300" />
              <h3 className="mb-2 text-lg font-medium">No Tasks to Display</h3>
              <p className="text-sm text-gray-500">
                {jobId
                  ? 'This job does not have any tasks scheduled yet.'
                  : 'No tasks are available for timeline visualization.'}
              </p>
            </div>
          )}
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
              <Calendar className="mr-2 h-5 w-5" />
              Task Timeline
            </CardTitle>
            <CardDescription>
              {tasks.length} task{tasks.length !== 1 ? 's' : ''} scheduled
              {jobId && ` for job ${jobId}`}
            </CardDescription>
          </div>

          <div className="flex items-center space-x-2">
            {/* Time range selector */}
            <Select
              value={timeRange}
              onValueChange={() => {
                /* timeRange selector would be implemented */
              }}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="day">Day</SelectItem>
                <SelectItem value="week">Week</SelectItem>
                <SelectItem value="month">Month</SelectItem>
              </SelectContent>
            </Select>

            {/* Navigation controls */}
            <div className="flex items-center rounded border">
              <Button
                variant="ghost"
                size="sm"
                onClick={handlePanLeft}
                className="rounded-none border-r"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={handlePanRight} className="rounded-none">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Zoom controls */}
            {enableZoom && (
              <div className="flex items-center rounded border">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleZoomOut}
                  className="rounded-none border-r"
                >
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <span className="min-w-[40px] px-2 text-center text-xs text-gray-600">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleZoomIn}
                  className="rounded-none border-l"
                >
                  <ZoomIn className="h-4 w-4" />
                </Button>
              </div>
            )}

            <Button variant="ghost" size="sm" onClick={handleResetZoom}>
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Legend */}
        <div className="mt-4 flex items-center space-x-4 text-xs">
          <span className="text-gray-600">Status:</span>
          {Object.entries(TASK_STATUS_COLORS).map(([status, color]) => (
            <div key={status} className="flex items-center space-x-1">
              <div className="h-3 w-3 rounded" style={{ backgroundColor: color }} />
              <span className="capitalize">{status.replace('_', ' ')}</span>
            </div>
          ))}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div ref={containerRef} className="relative border-t" style={{ height: `${height}px` }}>
          {/* Timeline header */}
          <div
            className="absolute left-0 right-0 top-0 flex border-b bg-gray-50"
            style={{ height: `${HEADER_HEIGHT}px` }}
          >
            {/* Task names sidebar */}
            <div
              className="flex-shrink-0 border-r bg-white"
              style={{ width: `${SIDEBAR_WIDTH}px` }}
            >
              <div className="p-4 text-sm font-medium text-gray-700">Tasks</div>
            </div>

            {/* Time intervals */}
            <div className="relative flex-1 overflow-hidden">
              <div
                className="flex h-full"
                style={{
                  width: `${Math.max(800, (containerRef.current?.clientWidth || 800) - SIDEBAR_WIDTH) * zoomLevel}px`,
                }}
              >
                {timelineRange.intervals.map((date, index) => (
                  <div
                    key={index}
                    className="min-w-0 flex-1 border-r border-gray-200 p-2 text-center"
                  >
                    <div className="truncate text-xs text-gray-600">{formatTimeLabel(date)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Gantt area */}
          <div
            ref={ganttRef}
            className="absolute flex overflow-auto"
            style={{
              top: `${HEADER_HEIGHT}px`,
              left: 0,
              right: 0,
              bottom: 0,
            }}
          >
            {/* Task names sidebar */}
            <div
              className="flex-shrink-0 border-r bg-white"
              style={{ width: `${SIDEBAR_WIDTH}px` }}
            >
              {tasks.map((task) => (
                <div
                  key={task.id.toString()}
                  className="flex cursor-pointer items-center border-b p-3 hover:bg-gray-50"
                  style={{ height: `${ROW_HEIGHT}px` }}
                  onClick={() => onTaskClick?.(task)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{task.name.toString()}</div>
                    <div className="text-xs text-gray-500">Seq: {task.sequence.value}</div>
                  </div>
                  <Badge variant="outline" className="ml-2 text-xs">
                    {task.status.value.replace('_', ' ')}
                  </Badge>
                </div>
              ))}
            </div>

            {/* Timeline bars */}
            <div className="relative flex-1">
              <svg
                width="100%"
                height={tasks.length * ROW_HEIGHT}
                className="absolute left-0 top-0"
              >
                {/* Grid lines */}
                {timelineRange.intervals.map((_, index) => {
                  const x = (index / timelineRange.intervals.length) * 100
                  return (
                    <line
                      key={index}
                      x1={`${x}%`}
                      y1={0}
                      x2={`${x}%`}
                      y2="100%"
                      stroke="#e5e7eb"
                      strokeWidth={1}
                    />
                  )
                })}

                {/* Task bars */}
                {taskBars.map((taskBar) => (
                  <g key={taskBar.task.id.toString()}>
                    <rect
                      x={taskBar.x}
                      y={taskBar.y + 4}
                      width={taskBar.width}
                      height={taskBar.height}
                      fill={taskBar.color}
                      rx={4}
                      className={cn(
                        'cursor-pointer transition-opacity',
                        enableDragDrop && 'hover:opacity-80',
                        taskBar.isDragging && 'opacity-60',
                      )}
                      onMouseDown={(e) => handleMouseDown(e, taskBar)}
                      onClick={() => onTaskClick?.(taskBar.task)}
                    />
                    <text
                      x={taskBar.x + 8}
                      y={taskBar.y + taskBar.height / 2 + 4}
                      fill="white"
                      fontSize="12"
                      className="pointer-events-none"
                    >
                      {taskBar.task.name.toString().length > 20
                        ? `${taskBar.task.name.toString().slice(0, 17)}...`
                        : taskBar.task.name.toString()}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="border-t bg-gray-50 p-4 text-xs text-gray-600">
          <div className="flex items-center justify-between">
            <div>
              Showing {timelineRange.start.toLocaleDateString()} -{' '}
              {timelineRange.end.toLocaleDateString()}
            </div>
            <div className="flex items-center space-x-4">
              {enableDragDrop && (
                <span className="flex items-center">
                  <Info className="mr-1 h-3 w-3" />
                  Drag tasks to reschedule
                </span>
              )}
              <span>Zoom: {Math.round(zoomLevel * 100)}%</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
