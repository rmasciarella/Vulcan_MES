'use client'

import { useState, useMemo, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { Input } from '@/shared/ui/input'
import { Grid3X3, AlertTriangle, Filter, Search, Plus, Edit } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

interface ResourceAllocation {
  id: string
  taskId: string
  taskName: string
  resourceId: string
  resourceName: string
  resourceType: 'machine' | 'operator' | 'workcell'
  department: string
  startTime: Date
  endTime: Date
  duration: number // in hours
  status: 'planned' | 'confirmed' | 'in_progress' | 'completed' | 'conflict'
  priority: 'low' | 'medium' | 'high' | 'critical'
  utilization: number // percentage of resource capacity
  skillsRequired?: string[]
  dependencies?: string[]
}

interface ResourceCapacity {
  id: string
  name: string
  type: 'machine' | 'operator' | 'workcell'
  department: string
  totalCapacity: number
  availableShifts: string[]
  skills?: string[]
  maintenanceSchedule?: Array<{ start: Date; end: Date; type: string }>
}

interface ResourceAllocationMatrixProps {
  timeRange?: '1d' | '3d' | '1w' | '2w' | '1m'
  department?: string
  resourceType?: 'all' | 'machine' | 'operator' | 'workcell'
  showConflicts?: boolean
  enableDragDrop?: boolean
  height?: number
  className?: string
  onAllocationClick?: (allocation: ResourceAllocation) => void
  onAllocationUpdate?: (id: string, updates: Partial<ResourceAllocation>) => void
}

// Mock data generators
const generateMockResources = (): ResourceCapacity[] => {
  return [
    {
      id: 'laser-1',
      name: 'Laser Cutter 1',
      type: 'machine',
      department: 'Cutting',
      totalCapacity: 24, // 24 hours per day
      availableShifts: ['day', 'night'],
    },
    {
      id: 'laser-2',
      name: 'Laser Cutter 2',
      type: 'machine',
      department: 'Cutting',
      totalCapacity: 24,
      availableShifts: ['day', 'evening'],
    },
    {
      id: 'assembly-a',
      name: 'Assembly Station A',
      type: 'machine',
      department: 'Assembly',
      totalCapacity: 16, // 2 shifts
      availableShifts: ['day', 'evening'],
    },
    {
      id: 'op-alice',
      name: 'Alice Johnson',
      type: 'operator',
      department: 'Cutting',
      totalCapacity: 8, // 8 hour shift
      availableShifts: ['day'],
      skills: ['laser_operation', 'quality_control'],
    },
    {
      id: 'op-bob',
      name: 'Bob Smith',
      type: 'operator',
      department: 'Assembly',
      totalCapacity: 8,
      availableShifts: ['evening'],
      skills: ['assembly', 'testing'],
    },
    {
      id: 'wc-cutting',
      name: 'Cutting Workcell',
      type: 'workcell',
      department: 'Cutting',
      totalCapacity: 4, // 4 concurrent tasks
      availableShifts: ['day', 'evening', 'night'],
    },
    {
      id: 'wc-assembly',
      name: 'Assembly Workcell',
      type: 'workcell',
      department: 'Assembly',
      totalCapacity: 3,
      availableShifts: ['day', 'evening'],
    },
  ]
}

const generateMockAllocations = (resources: ResourceCapacity[]): ResourceAllocation[] => {
  const allocations: ResourceAllocation[] = []
  const baseTime = new Date()
  baseTime.setHours(8, 0, 0, 0) // Start at 8 AM

  resources.forEach((resource, resourceIndex) => {
    // Generate 3-5 allocations per resource
    const allocationCount = Math.floor(Math.random() * 3) + 3

    for (let i = 0; i < allocationCount; i++) {
      const startHour = 8 + i * 4 + Math.floor(Math.random() * 2) // Some overlap
      const duration = Math.floor(Math.random() * 4) + 1 // 1-4 hours

      const startTime = new Date(baseTime)
      startTime.setHours(startHour + (resourceIndex % 2) * 12) // Spread across days

      const endTime = new Date(startTime)
      endTime.setHours(startTime.getHours() + duration)

      const priorities = ['low', 'medium', 'high', 'critical'] as const
      const statuses = ['planned', 'confirmed', 'in_progress'] as const

      // Detect conflicts (overlapping allocations)
      const hasConflict = allocations.some(
        (existing) =>
          existing.resourceId === resource.id &&
          ((startTime >= existing.startTime && startTime < existing.endTime) ||
            (endTime > existing.startTime && endTime <= existing.endTime) ||
            (startTime <= existing.startTime && endTime >= existing.endTime)),
      )

      allocations.push({
        id: `alloc-${resource.id}-${i}`,
        taskId: `task-${resourceIndex * 10 + i}`,
        taskName: `Task ${String.fromCharCode(65 + resourceIndex)}${i + 1}`,
        resourceId: resource.id,
        resourceName: resource.name,
        resourceType: resource.type,
        department: resource.department,
        startTime,
        endTime,
        duration,
        status: hasConflict ? 'conflict' : (statuses[Math.floor(Math.random() * statuses.length)] ?? 'planned'),
        priority: priorities[Math.floor(Math.random() * priorities.length)] ?? 'low',
        utilization: Math.floor(Math.random() * 40) + 60, // 60-100%
        ...(resource.skills
          ? { skillsRequired: resource.skills.slice(0, Math.floor(Math.random() * 2) + 1) }
          : {}),
      })
    }
  })

  return allocations
}

const STATUS_COLORS = {
  planned: 'bg-blue-100 text-blue-800 border-blue-200',
  confirmed: 'bg-green-100 text-green-800 border-green-200',
  in_progress: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  completed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  conflict: 'bg-red-100 text-red-800 border-red-200',
} as const

const PRIORITY_COLORS = {
  low: 'border-l-gray-400',
  medium: 'border-l-blue-400',
  high: 'border-l-orange-400',
  critical: 'border-l-red-500',
} as const

/**
 * Resource Allocation Matrix - Capacity planning and scheduling visualization
 * Features:
 * - Matrix view of resources vs time slots
 * - Drag and drop allocation editing
 * - Conflict detection and highlighting
 * - Capacity utilization visualization
 * - Multi-resource scheduling
 * - Department and resource type filtering
 * - Real-time availability updates
 * - Manufacturing constraint validation
 */
export function ResourceAllocationMatrix({
  timeRange = '1w',
  department,
  resourceType = 'all',
  showConflicts = true,
  enableDragDrop = true,
  height = 600,
  className,
  onAllocationClick,
  onAllocationUpdate: _onAllocationUpdate,
}: ResourceAllocationMatrixProps) {
  const [isLoading, _setIsLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedPriority, setSelectedPriority] = useState<string>('all')
  const [viewMode, setViewMode] = useState<'grid' | 'timeline'>('grid')

  // Mock data - in real implementation, this would come from hooks
  const resources = useMemo(() => {
    const allResources = generateMockResources()
    return allResources.filter((resource) => {
      if (department && resource.department !== department) return false
      if (resourceType !== 'all' && resource.type !== resourceType) return false
      if (searchTerm && !resource.name.toLowerCase().includes(searchTerm.toLowerCase()))
        return false
      return true
    })
  }, [department, resourceType, searchTerm])

  const allocations = useMemo(() => {
    const allAllocations = generateMockAllocations(resources)
    return allAllocations.filter((allocation) => {
      if (selectedPriority !== 'all' && allocation.priority !== selectedPriority) return false
      return true
    })
  }, [resources, selectedPriority])

  // Generate time slots based on time range
  const timeSlots = useMemo(() => {
    const slots = []
    const now = new Date()
    const startTime = new Date(now)
    startTime.setHours(8, 0, 0, 0) // Start at 8 AM today

    const days = timeRange === '1d' ? 1 : timeRange === '3d' ? 3 : timeRange === '1w' ? 7 : 14
    const hoursPerSlot = timeRange === '1d' ? 1 : 4 // 1 hour for day view, 4 hours for longer periods

    for (let day = 0; day < days; day++) {
      for (let hour = 8; hour < 20; hour += hoursPerSlot) {
        // 8 AM to 8 PM
        const slotTime = new Date(startTime)
        slotTime.setDate(startTime.getDate() + day)
        slotTime.setHours(hour)

        slots.push({
          time: slotTime,
          label:
            timeRange === '1d'
              ? slotTime.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true })
              : `${slotTime.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${slotTime.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true })}`,
        })
      }
    }

    return slots
  }, [timeRange])

  // Calculate resource utilization for each time slot
  const getSlotUtilization = useCallback(
    (resourceId: string, slotTime: Date) => {
      const resourceAllocations = allocations.filter((a) => a.resourceId === resourceId)
      const slotEnd = new Date(slotTime)
      slotEnd.setHours(slotTime.getHours() + (timeRange === '1d' ? 1 : 4))

      const overlapping = resourceAllocations.filter(
        (allocation) => allocation.startTime < slotEnd && allocation.endTime > slotTime,
      )

      if (overlapping.length === 0) return { utilization: 0, allocations: [], hasConflict: false }

      // Calculate total utilization percentage
      const totalUtilization = overlapping.reduce((sum, allocation) => {
        const overlapStart = new Date(Math.max(allocation.startTime.getTime(), slotTime.getTime()))
        const overlapEnd = new Date(Math.min(allocation.endTime.getTime(), slotEnd.getTime()))
        const overlapHours = (overlapEnd.getTime() - overlapStart.getTime()) / (1000 * 60 * 60)
        const slotHours = (slotEnd.getTime() - slotTime.getTime()) / (1000 * 60 * 60)

        return sum + (overlapHours / slotHours) * 100
      }, 0)

      const hasConflict = overlapping.length > 1 || overlapping.some((a) => a.status === 'conflict')

      return {
        utilization: Math.min(totalUtilization, 100),
        allocations: overlapping,
        hasConflict,
      }
    },
    [allocations, timeRange],
  )

  const renderGridView = () => (
    <div className="overflow-x-auto">
      <div className="min-w-max">
        {/* Header with time slots */}
        <div className="sticky top-0 z-10 flex border-b bg-gray-50">
          <div className="w-48 border-r p-3 text-sm font-medium">Resource</div>
          {timeSlots.map((slot, index) => (
            <div key={index} className="w-32 border-r p-2 text-center text-xs">
              {slot.label}
            </div>
          ))}
        </div>

        {/* Resource rows */}
        {resources.map((resource) => (
          <div key={resource.id} className="flex border-b hover:bg-gray-50">
            <div className="w-48 border-r p-3">
              <div className="truncate text-sm font-medium">{resource.name}</div>
              <div className="text-xs text-gray-500">{resource.department}</div>
              <Badge variant="outline" className="mt-1 text-xs">
                {resource.type}
              </Badge>
            </div>

            {timeSlots.map((slot, slotIndex) => {
              const utilization = getSlotUtilization(resource.id, slot.time)

              return (
                <div
                  key={slotIndex}
                  className={cn(
                    'relative min-h-[60px] w-32 cursor-pointer border-r p-1 transition-colors',
                    utilization.utilization > 0 && 'hover:bg-gray-100',
                  )}
                  onClick={() => {
                    // Handle slot click for creating new allocation
                    console.log(`Clicked slot for ${resource.name} at ${slot.time}`)
                  }}
                >
                  {utilization.allocations.map((allocation, _allocIndex) => (
                    <div
                      key={allocation.id}
                      className={cn(
                        'mb-1 cursor-pointer rounded border-l-2 p-1 text-xs',
                        STATUS_COLORS[allocation.status],
                        PRIORITY_COLORS[allocation.priority],
                        utilization.hasConflict && 'ring-2 ring-red-300',
                      )}
                      onClick={(e) => {
                        e.stopPropagation()
                        onAllocationClick?.(allocation)
                      }}
                      title={`${allocation.taskName} - ${allocation.startTime.toLocaleTimeString()} to ${allocation.endTime.toLocaleTimeString()}`}
                    >
                      <div className="truncate font-medium">{allocation.taskName}</div>
                      <div className="truncate text-gray-600">{allocation.utilization}% util</div>
                    </div>
                  ))}

                  {utilization.utilization > 0 && (
                    <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200">
                      <div
                        className={cn(
                          'h-full transition-all',
                          utilization.utilization > 90
                            ? 'bg-red-500'
                            : utilization.utilization > 70
                              ? 'bg-yellow-500'
                              : 'bg-green-500',
                        )}
                        style={{ width: `${Math.min(utilization.utilization, 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )

  const renderTimelineView = () => (
    <div className="space-y-4">
      {resources.map((resource) => {
        const resourceAllocations = allocations.filter((a) => a.resourceId === resource.id)
        const sortedAllocations = resourceAllocations.sort(
          (a, b) => a.startTime.getTime() - b.startTime.getTime(),
        )

        return (
          <Card key={resource.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">{resource.name}</CardTitle>
                  <CardDescription>
                    {resource.department} • {resource.type} • {sortedAllocations.length} allocation
                    {sortedAllocations.length !== 1 ? 's' : ''}
                  </CardDescription>
                </div>
                <Badge
                  variant={
                    sortedAllocations.some((a) => a.status === 'conflict')
                      ? 'destructive'
                      : 'default'
                  }
                >
                  {sortedAllocations.some((a) => a.status === 'conflict') ? 'Conflicts' : 'OK'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {sortedAllocations.map((allocation) => (
                  <div
                    key={allocation.id}
                    className={cn(
                      'flex cursor-pointer items-center justify-between rounded border border-l-4 p-3 hover:bg-gray-50',
                      PRIORITY_COLORS[allocation.priority],
                    )}
                    onClick={() => onAllocationClick?.(allocation)}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">{allocation.taskName}</span>
                        <Badge variant="outline" className={STATUS_COLORS[allocation.status]}>
                          {allocation.status}
                        </Badge>
                        {allocation.status === 'conflict' && (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                      <div className="mt-1 text-sm text-gray-600">
                        {allocation.startTime.toLocaleString()} -{' '}
                        {allocation.endTime.toLocaleString()}
                        <span className="ml-2">
                          • {allocation.duration}h • {allocation.utilization}% utilization
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge
                        variant={allocation.priority === 'critical' ? 'destructive' : 'outline'}
                      >
                        {allocation.priority}
                      </Badge>
                      {enableDragDrop && (
                        <Button variant="ghost" size="sm">
                          <Edit className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}

                {sortedAllocations.length === 0 && (
                  <div className="py-4 text-center text-gray-500">No allocations scheduled</div>
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Grid3X3 className="mr-2 h-5 w-5" />
            Resource Allocation Matrix
          </CardTitle>
          <CardDescription>Loading allocation data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  const conflictCount = allocations.filter((a) => a.status === 'conflict').length
  const totalUtilization =
    resources.reduce((sum, resource) => {
      const resourceAllocations = allocations.filter((a) => a.resourceId === resource.id)
      const avgUtilization =
        resourceAllocations.reduce((total, allocation) => total + allocation.utilization, 0) /
        (resourceAllocations.length || 1)
      return sum + avgUtilization
    }, 0) / (resources.length || 1)

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center">
              <Grid3X3 className="mr-2 h-5 w-5" />
              Resource Allocation Matrix
            </CardTitle>
            <CardDescription>
              {resources.length} resource{resources.length !== 1 ? 's' : ''} • {allocations.length}{' '}
              allocation{allocations.length !== 1 ? 's' : ''}
              {conflictCount > 0 && (
                <span className="ml-2 text-red-600">
                  • {conflictCount} conflict{conflictCount !== 1 ? 's' : ''}
                </span>
              )}
            </CardDescription>
          </div>

          <div className="flex items-center space-x-2">
            <Select
              value={viewMode}
              onValueChange={(value) => setViewMode(value as 'grid' | 'timeline')}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="grid">Grid</SelectItem>
                <SelectItem value="timeline">Timeline</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={timeRange}
              onValueChange={() => {
                /* Time range change handler */
              }}
            >
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1d">1 Day</SelectItem>
                <SelectItem value="3d">3 Days</SelectItem>
                <SelectItem value="1w">1 Week</SelectItem>
                <SelectItem value="2w">2 Weeks</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm">
              <Plus className="mr-1 h-4 w-4" />
              New
            </Button>
          </div>
        </div>

        {/* Filters and search */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-gray-400" />
            <Input
              placeholder="Search resources..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          <Select value={selectedPriority} onValueChange={(v) => setSelectedPriority(v)}>
            <SelectTrigger>
              <Filter className="mr-2 h-4 w-4" />
              <SelectValue placeholder="All Priorities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center">
              <div className="mr-2 h-3 w-3 rounded bg-green-500" />
              <span>Available</span>
            </div>
            <div className="flex items-center">
              <div className="mr-2 h-3 w-3 rounded bg-yellow-500" />
              <span>Busy</span>
            </div>
            <div className="flex items-center">
              <div className="mr-2 h-3 w-3 rounded bg-red-500" />
              <span>Overbooked</span>
            </div>
          </div>
        </div>

        {/* Summary metrics */}
        {showConflicts && conflictCount > 0 && (
          <Alert variant="destructive" className="mt-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {conflictCount} resource conflict{conflictCount !== 1 ? 's' : ''} detected. Review
              overlapping allocations and adjust scheduling.
            </AlertDescription>
          </Alert>
        )}

        <div className="mt-4 flex items-center justify-between rounded bg-gray-50 p-3">
          <div className="text-sm">
            <span className="font-medium">Average Utilization:</span> {totalUtilization.toFixed(1)}%
          </div>
          <div className="text-sm">
            <span className="font-medium">Efficiency Target:</span> 85%
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div style={{ height: `${height}px` }} className="overflow-y-auto">
          {viewMode === 'grid' ? renderGridView() : renderTimelineView()}
        </div>
      </CardContent>
    </Card>
  )
}
