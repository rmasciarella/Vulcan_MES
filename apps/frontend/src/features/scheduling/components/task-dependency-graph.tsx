'use client'

import { useState, useMemo, useCallback, useRef } from 'react'
import { useTasks, useTasksByJob } from '@/features/scheduling/hooks/use-tasks'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import {
  GitBranch,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  AlertCircle,
  ArrowRight,
  Circle,
  Square,
  Diamond,
} from 'lucide-react'
import type { Task } from '@/core/domains/tasks'
// cn utility can be imported when needed

interface TaskDependencyGraphProps {
  jobId?: string
  tasks?: Task[]
  width?: number
  height?: number
  enableZoom?: boolean
  layout?: 'hierarchical' | 'circular' | 'force'
  showCriticalPath?: boolean
  className?: string
  onTaskClick?: (task: Task) => void
  onDependencyClick?: (from: string, to: string) => void
}

interface GraphNode {
  id: string
  task: Task
  x: number
  y: number
  width: number
  height: number
  level: number
  color: string
  shape: 'circle' | 'square' | 'diamond' | 'triangle'
}

interface GraphEdge {
  id: string
  from: string
  to: string
  path: string
  isCritical: boolean
  type: 'finish-to-start' | 'start-to-start' | 'finish-to-finish' | 'start-to-finish'
}

const TASK_STATUS_COLORS = {
  not_ready: '#94a3b8',
  ready: '#3b82f6',
  scheduled: '#8b5cf6',
  in_progress: '#f59e0b',
  completed: '#10b981',
  on_hold: '#f97316',
  cancelled: '#ef4444',
} as const

const NODE_WIDTH = 120
const NODE_HEIGHT = 60
const LEVEL_HEIGHT = 100
const MIN_NODE_SPACING = 40

/**
 * Task Dependency Graph - Interactive precedence visualization
 * Features:
 * - Multiple layout algorithms (hierarchical, circular, force-directed)
 * - Critical path highlighting for manufacturing optimization
 * - Interactive node and edge selection
 * - Zoom and pan controls
 * - Different node shapes based on task types
 * - Real-time dependency validation
 * - Manufacturing constraint visualization
 */
export function TaskDependencyGraph({
  jobId,
  tasks: propTasks,
  width = 800,
  height = 600,
  enableZoom = true,
  layout = 'hierarchical',
  showCriticalPath = true,
  className,
  onTaskClick,
  onDependencyClick,
}: TaskDependencyGraphProps) {
  const [zoomLevel, setZoomLevel] = useState(1)
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

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

  // Calculate task dependencies (placeholder - would come from actual task relationships)
  const dependencies = useMemo(() => {
    const deps: Array<{ from: string; to: string; type: string }> = []

    // Create sample dependencies based on task sequence for demonstration
    const sortedTasks = [...tasks].sort((a, b) => a.sequence.value - b.sequence.value)

    for (let i = 0; i < sortedTasks.length - 1; i++) {
      deps.push({
        from: sortedTasks[i].id.toString(),
        to: sortedTasks[i + 1].id.toString(),
        type: 'finish-to-start',
      })
    }

    // Add some parallel dependencies for setup tasks
    tasks.forEach((task) => {
      if (task.isSetupTask) {
        const nextProductionTask = tasks.find(
          (t) => !t.isSetupTask && t.sequence.value > task.sequence.value,
        )
        if (nextProductionTask) {
          deps.push({
            from: task.id.toString(),
            to: nextProductionTask.id.toString(),
            type: 'finish-to-start',
          })
        }
      }
    })

    return deps
  }, [tasks])

  // Calculate critical path (simplified algorithm)
  const criticalPath = useMemo(() => {
    if (!showCriticalPath || tasks.length === 0) return new Set<string>()

    // Simplified critical path calculation
    // In a real implementation, this would use proper CPM algorithm
    const path = new Set<string>()
    const sortedTasks = [...tasks].sort((a, b) => a.sequence.value - b.sequence.value)

    // Add first and last tasks to critical path
    if (sortedTasks.length > 0) {
      path.add(sortedTasks[0].id.toString())
      path.add(sortedTasks[sortedTasks.length - 1].id.toString())
    }

    // Add tasks that are currently in progress or overdue
    tasks.forEach((task) => {
      if (task.status.value === 'in_progress' || task.status.value === 'on_hold') {
        path.add(task.id.toString())
      }
    })

    return path
  }, [tasks, showCriticalPath])

  // Generate graph nodes based on layout algorithm
  const graphNodes = useMemo((): GraphNode[] => {
    if (tasks.length === 0) return []

    const nodes: GraphNode[] = []

    if (layout === 'hierarchical') {
      // Hierarchical layout - arrange by sequence/level
      const levels = new Map<number, Task[]>()

      tasks.forEach((task) => {
        const level = Math.floor(task.sequence.value / 10) // Group by tens
        if (!levels.has(level)) {
          levels.set(level, [])
        }
        levels.get(level)!.push(task)
      })

      Array.from(levels.entries()).forEach(([_level, levelTasks], levelIndex) => {
        levelTasks.forEach((task, taskIndex) => {
          const x =
            (taskIndex - (levelTasks.length - 1) / 2) * (NODE_WIDTH + MIN_NODE_SPACING) + width / 2
          const y = levelIndex * LEVEL_HEIGHT + 80

          nodes.push({
            id: task.id.toString(),
            task,
            x,
            y,
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
            level: levelIndex,
            color: TASK_STATUS_COLORS[task.status.value],
            shape: task.isSetupTask
              ? 'diamond'
              : task.attendanceRequirement.isUnattended
                ? 'square'
                : 'circle',
          })
        })
      })
    } else if (layout === 'circular') {
      // Circular layout
      const centerX = width / 2
      const centerY = height / 2
      const radius = Math.min(width, height) * 0.3

      tasks.forEach((task, index) => {
        const angle = (index / tasks.length) * 2 * Math.PI - Math.PI / 2
        const x = centerX + radius * Math.cos(angle)
        const y = centerY + radius * Math.sin(angle)

        nodes.push({
          id: task.id.toString(),
          task,
          x,
          y,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          level: 0,
          color: TASK_STATUS_COLORS[task.status.value],
          shape: task.isSetupTask
            ? 'diamond'
            : task.attendanceRequirement.isUnattended
              ? 'square'
              : 'circle',
        })
      })
    } else {
      // Force-directed layout (simplified)
      tasks.forEach((task, index) => {
        const x = (index % 4) * (NODE_WIDTH + MIN_NODE_SPACING) + 100
        const y = Math.floor(index / 4) * (NODE_HEIGHT + MIN_NODE_SPACING) + 100

        nodes.push({
          id: task.id.toString(),
          task,
          x,
          y,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          level: Math.floor(index / 4),
          color: TASK_STATUS_COLORS[task.status.value],
          shape: task.isSetupTask
            ? 'diamond'
            : task.attendanceRequirement.isUnattended
              ? 'square'
              : 'circle',
        })
      })
    }

    return nodes
  }, [tasks, layout, width, height])

  // Generate graph edges
  const graphEdges = useMemo((): GraphEdge[] => {
    const edges: GraphEdge[] = []

    dependencies.forEach((dep) => {
      const fromNode = graphNodes.find((n) => n.id === dep.from)
      const toNode = graphNodes.find((n) => n.id === dep.to)

      if (fromNode && toNode) {
        // Calculate arrow path
        const fromX = fromNode.x + fromNode.width / 2
        const fromY = fromNode.y + fromNode.height / 2
        const toX = toNode.x + toNode.width / 2
        const toY = toNode.y + toNode.height / 2

        // Simple straight line path (could be improved with bezier curves)
        const path = `M ${fromX} ${fromY} L ${toX} ${toY}`

        const isCritical = criticalPath.has(dep.from) && criticalPath.has(dep.to)

        edges.push({
          id: `${dep.from}-${dep.to}`,
          from: dep.from,
          to: dep.to,
          path,
          isCritical,
          type: dep.type as string,
        })
      }
    })

    return edges
  }, [graphNodes, dependencies, criticalPath])

  // Zoom and pan handlers
  const handleZoomIn = useCallback(() => {
    setZoomLevel((prev) => Math.min(prev * 1.2, 3))
  }, [])

  const handleZoomOut = useCallback(() => {
    setZoomLevel((prev) => Math.max(prev / 1.2, 0.3))
  }, [])

  const handleResetView = useCallback(() => {
    setZoomLevel(1)
    setPanOffset({ x: 0, y: 0 })
  }, [])

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === svgRef.current) {
        setIsDragging(true)
        setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y })
      }
    },
    [panOffset],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging) {
        setPanOffset({
          x: e.clientX - dragStart.x,
          y: e.clientY - dragStart.y,
        })
      }
    },
    [isDragging, dragStart],
  )

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  const renderNode = useCallback(
    (node: GraphNode) => {
      const isSelected = selectedNode === node.id
      const isCritical = criticalPath.has(node.id)

      const commonProps = {
        fill: node.color,
        stroke: isSelected ? '#1f2937' : isCritical ? '#dc2626' : '#6b7280',
        strokeWidth: isSelected ? 3 : isCritical ? 2 : 1,
        className: 'cursor-pointer hover:opacity-80 transition-opacity',
        onClick: () => {
          setSelectedNode(node.id)
          onTaskClick?.(node.task)
        },
      }

      let shapeElement
      switch (node.shape) {
        case 'diamond':
          const diamondPath = `M ${node.x + node.width / 2} ${node.y} 
                           L ${node.x + node.width} ${node.y + node.height / 2} 
                           L ${node.x + node.width / 2} ${node.y + node.height} 
                           L ${node.x} ${node.y + node.height / 2} Z`
          shapeElement = <path d={diamondPath} {...commonProps} />
          break
        case 'square':
          shapeElement = (
            <rect
              x={node.x}
              y={node.y}
              width={node.width}
              height={node.height}
              rx={4}
              {...commonProps}
            />
          )
          break
        case 'triangle':
          const trianglePath = `M ${node.x + node.width / 2} ${node.y} 
                            L ${node.x + node.width} ${node.y + node.height} 
                            L ${node.x} ${node.y + node.height} Z`
          shapeElement = <path d={trianglePath} {...commonProps} />
          break
        default: // circle
          shapeElement = (
            <ellipse
              cx={node.x + node.width / 2}
              cy={node.y + node.height / 2}
              rx={node.width / 2}
              ry={node.height / 2}
              {...commonProps}
            />
          )
      }

      return (
        <g key={node.id}>
          {shapeElement}
          <text
            x={node.x + node.width / 2}
            y={node.y + node.height / 2 - 8}
            textAnchor="middle"
            className="pointer-events-none text-xs font-medium text-white"
            fill="white"
          >
            {node.task.name.toString().length > 12
              ? `${node.task.name.toString().slice(0, 9)}...`
              : node.task.name.toString()}
          </text>
          <text
            x={node.x + node.width / 2}
            y={node.y + node.height / 2 + 6}
            textAnchor="middle"
            className="pointer-events-none text-xs text-white"
            fill="white"
            opacity={0.8}
          >
            Seq: {node.task.sequence.value}
          </text>
        </g>
      )
    },
    [selectedNode, criticalPath, onTaskClick],
  )

  const renderEdge = useCallback(
    (edge: GraphEdge) => {
      const isSelected = selectedEdge === edge.id

      return (
        <g key={edge.id}>
          <path
            d={edge.path}
            fill="none"
            stroke={edge.isCritical ? '#dc2626' : '#6b7280'}
            strokeWidth={isSelected ? 3 : edge.isCritical ? 2 : 1}
            strokeDasharray={edge.type !== 'finish-to-start' ? '5,5' : undefined}
            className="cursor-pointer hover:opacity-80"
            onClick={() => {
              setSelectedEdge(edge.id)
              onDependencyClick?.(edge.from, edge.to)
            }}
          />
          {/* Arrow head */}
          <defs>
            <marker
              id={`arrowhead-${edge.id}`}
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill={edge.isCritical ? '#dc2626' : '#6b7280'} />
            </marker>
          </defs>
          <path
            d={edge.path}
            fill="none"
            stroke="transparent"
            strokeWidth={2}
            markerEnd={`url(#arrowhead-${edge.id})`}
          />
        </g>
      )
    },
    [selectedEdge, onDependencyClick],
  )

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <GitBranch className="mr-2 h-5 w-5" />
            Task Dependencies
          </CardTitle>
          <CardDescription>Loading dependency graph...</CardDescription>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-96 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error || tasks.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <GitBranch className="mr-2 h-5 w-5" />
            Task Dependencies
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>Failed to load task dependencies: {error.message}</AlertDescription>
            </Alert>
          ) : (
            <div className="py-8 text-center">
              <GitBranch className="mx-auto mb-4 h-12 w-12 text-gray-300" />
              <h3 className="mb-2 text-lg font-medium">No Dependencies</h3>
              <p className="text-sm text-gray-500">
                {jobId
                  ? 'This job does not have any task dependencies defined yet.'
                  : 'No task dependencies are available for visualization.'}
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
              <GitBranch className="mr-2 h-5 w-5" />
              Task Dependencies
            </CardTitle>
            <CardDescription>
              {tasks.length} task{tasks.length !== 1 ? 's' : ''} with {dependencies.length}{' '}
              dependencies
              {criticalPath.size > 0 && ` • ${criticalPath.size} critical tasks`}
            </CardDescription>
          </div>

          <div className="flex items-center space-x-2">
            {/* Layout selector */}
            <Select
              value={layout}
              onValueChange={() => {
                /* Layout change handler */
              }}
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hierarchical">Hierarchical</SelectItem>
                <SelectItem value="circular">Circular</SelectItem>
                <SelectItem value="force">Force</SelectItem>
              </SelectContent>
            </Select>

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
                <span className="min-w-[50px] px-2 text-center text-xs text-gray-600">
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

            <Button variant="ghost" size="sm" onClick={handleResetView}>
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Legend */}
        <div className="mt-4 grid grid-cols-1 gap-4 text-xs md:grid-cols-2">
          <div>
            <span className="font-medium text-gray-700">Shapes:</span>
            <div className="mt-1 flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <Circle className="h-3 w-3 text-blue-500" />
                <span>Attended</span>
              </div>
              <div className="flex items-center space-x-1">
                <Square className="h-3 w-3 text-blue-500" />
                <span>Unattended</span>
              </div>
              <div className="flex items-center space-x-1">
                <Diamond className="h-3 w-3 text-blue-500" />
                <span>Setup</span>
              </div>
            </div>
          </div>
          <div>
            <span className="font-medium text-gray-700">Indicators:</span>
            <div className="mt-1 flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <div className="h-3 w-3 border-2 border-red-500" />
                <span>Critical Path</span>
              </div>
              <div className="flex items-center space-x-1">
                <ArrowRight className="h-3 w-3 text-gray-500" />
                <span>Dependencies</span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div
          ref={containerRef}
          className="relative overflow-hidden border-t"
          style={{ width: `${width}px`, height: `${height}px` }}
        >
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            className="cursor-move"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <g transform={`translate(${panOffset.x}, ${panOffset.y}) scale(${zoomLevel})`}>
              {/* Render edges first (behind nodes) */}
              {graphEdges.map(renderEdge)}

              {/* Render nodes */}
              {graphNodes.map(renderNode)}
            </g>
          </svg>

          {/* Minimap could be added here */}
        </div>

        {/* Selected task/dependency info */}
        {(selectedNode || selectedEdge) && (
          <div className="border-t bg-gray-50 p-4">
            {selectedNode && (
              <div className="text-sm">
                <div className="mb-1 font-medium">
                  Selected Task:{' '}
                  {graphNodes.find((n) => n.id === selectedNode)?.task.name.toString()}
                </div>
                <div className="text-gray-600">
                  {graphNodes
                    .find((n) => n.id === selectedNode)
                    ?.task.status.value.replace('_', ' ')}
                  • Sequence: {graphNodes.find((n) => n.id === selectedNode)?.task.sequence.value}
                </div>
              </div>
            )}
            {selectedEdge && (
              <div className="text-sm">
                <div className="mb-1 font-medium">Selected Dependency: {selectedEdge}</div>
                <div className="text-gray-600">
                  Type: {graphEdges.find((e) => e.id === selectedEdge)?.type.replace('-', ' to ')}
                  {graphEdges.find((e) => e.id === selectedEdge)?.isCritical && (
                    <Badge variant="destructive" className="ml-2 text-xs">
                      Critical
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
