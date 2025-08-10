/**
 * Mock resource data utilities for testing ResourceAllocationMatrix
 * Moved from production components to test utilities
 */

export interface ResourceCapacity {
  id: string
  name: string
  type: 'machine' | 'operator' | 'workcell'
  department: string
  totalCapacity: number
  availableShifts: string[]
  skills?: string[]
  maintenanceSchedule?: Array<{ start: Date; end: Date; type: string }>
}

export interface ResourceAllocation {
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

/**
 * Generate mock resource capacity data for testing
 */
export const generateMockResources = (): ResourceCapacity[] => {
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

/**
 * Generate mock resource allocation data for testing
 */
export const generateMockAllocations = (resources: ResourceCapacity[]): ResourceAllocation[] => {
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