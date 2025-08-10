import React, { useMemo } from 'react'
import { Card } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { 
  useResourceAllocation, 
  useResources, 
  useUnallocatedTasks,
  useCreateAllocation 
} from '../hooks/use-resource-allocation'

interface MatrixCell {
  resourceId: string
  taskId?: string
  allocation?: any
  isCompatible: boolean
  utilizationConflict: boolean
}

export function ResourceAllocationMatrix() {
  const {
    selectedResources,
    selectedTasks,
    allocations,
    preferences,
    startDragging,
    stopDragging,
    isDragging,
    draggedItem,
  } = useResourceAllocation()

  const { resources } = useResources()
  const unallocatedTasks = useUnallocatedTasks()
  const createAllocationMutation = useCreateAllocation()

  // Create matrix data structure
  const matrixData = useMemo(() => {
    const matrix: MatrixCell[][] = []

    resources.forEach((resource, resourceIndex) => {
      const row: MatrixCell[] = []
      
      unallocatedTasks.forEach((task, taskIndex) => {
        // Check if resource is compatible with task
        const isCompatible = checkResourceTaskCompatibility(resource, task)
        
        // Check for utilization conflicts
        const utilizationConflict = checkUtilizationConflict(resource.id, task.id, allocations)
        
        // Check if there's already an allocation
        const existingAllocation = allocations.find(
          a => a.resourceId === resource.id && a.taskId === task.id
        )

        row.push({
          resourceId: resource.id,
          taskId: task.id,
          allocation: existingAllocation,
          isCompatible,
          utilizationConflict,
        })
      })

      matrix.push(row)
    })

    return matrix
  }, [resources, unallocatedTasks, allocations])

  const handleCellClick = (cell: MatrixCell) => {
    if (!cell.taskId || !cell.isCompatible) return

    if (cell.allocation) {
      // Already allocated - could show details or allow modification
      return
    }

    // Create new allocation
    const resource = resources.find(r => r.id === cell.resourceId)
    const task = unallocatedTasks.find(t => t.id === cell.taskId)
    
    if (resource && task) {
      const now = new Date()
      const endTime = new Date(now.getTime() + task.estimatedDuration * 60 * 1000)
      
      createAllocationMutation.mutate({
        resourceId: resource.id,
        resourceType: resource.type,
        taskId: task.id,
        jobId: task.jobId,
        startTime: now,
        endTime: endTime,
      })
    }
  }

  const handleDrop = (resourceId: string, taskId: string) => {
    if (!isDragging || !draggedItem || draggedItem.type !== 'task') return

    const resource = resources.find(r => r.id === resourceId)
    const task = unallocatedTasks.find(t => t.id === draggedItem.id)
    
    if (resource && task && checkResourceTaskCompatibility(resource, task)) {
      const now = new Date()
      const endTime = new Date(now.getTime() + task.estimatedDuration * 60 * 1000)
      
      createAllocationMutation.mutate({
        resourceId: resource.id,
        resourceType: resource.type,
        taskId: task.id,
        jobId: task.jobId,
        startTime: now,
        endTime: endTime,
      })
    }
    
    stopDragging()
  }

  if (resources.length === 0 || unallocatedTasks.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-gray-500">
          {resources.length === 0 ? 'No resources available' : 'No unallocated tasks found'}
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Resource-Task Allocation Matrix</h2>
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-green-100 border border-green-300 rounded"></div>
            <span>Compatible</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-red-100 border border-red-300 rounded"></div>
            <span>Incompatible</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-blue-100 border border-blue-500 rounded"></div>
            <span>Allocated</span>
          </div>
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="sticky left-0 bg-gray-50 p-3 text-left text-sm font-medium text-gray-700 border-r">
                  Resources
                </th>
                {unallocatedTasks.map((task) => (
                  <th
                    key={task.id}
                    className="p-3 text-left text-sm font-medium text-gray-700 min-w-[150px] border-r last:border-r-0"
                  >
                    <div>
                      <div className="font-medium">{task.name}</div>
                      <div className="text-xs text-gray-500">
                        {task.jobName} • {task.estimatedDuration}min
                      </div>
                      {task.requiredSkills.length > 0 && (
                        <div className="text-xs text-gray-400 mt-1">
                          Skills: {task.requiredSkills.slice(0, 2).join(', ')}
                          {task.requiredSkills.length > 2 && ` +${task.requiredSkills.length - 2}`}
                        </div>
                      )}
                      <Badge 
                        variant={task.priority > 3 ? 'destructive' : 'outline'}
                        className="text-xs mt-1"
                      >
                        P{task.priority}
                      </Badge>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrixData.map((row, resourceIndex) => {
                const resource = resources[resourceIndex]
                const isResourceSelected = selectedResources.includes(resource.id)
                
                return (
                  <tr
                    key={resource.id}
                    className={`border-b hover:bg-gray-50 ${
                      isResourceSelected ? 'bg-blue-50' : ''
                    }`}
                  >
                    <td className="sticky left-0 bg-white p-3 border-r">
                      <div>
                        <div className="font-medium">{resource.name}</div>
                        <div className="text-xs text-gray-500 capitalize">
                          {resource.type} • {resource.status}
                        </div>
                        {resource.skills.length > 0 && (
                          <div className="text-xs text-gray-400 mt-1">
                            Skills: {resource.skills.slice(0, 2).join(', ')}
                            {resource.skills.length > 2 && ` +${resource.skills.length - 2}`}
                          </div>
                        )}
                        <div className="text-xs text-gray-500 mt-1">
                          Utilization: {resource.utilization}%
                        </div>
                      </div>
                    </td>
                    {row.map((cell, taskIndex) => {
                      const task = unallocatedTasks[taskIndex]
                      const isTaskSelected = selectedTasks.includes(task.id)
                      
                      return (
                        <td
                          key={`${cell.resourceId}-${cell.taskId}`}
                          className="p-1 border-r last:border-r-0 relative"
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => cell.taskId && handleDrop(cell.resourceId, cell.taskId)}
                        >
                          <div
                            className={`
                              w-full h-20 rounded border-2 cursor-pointer transition-all flex items-center justify-center text-xs
                              ${cell.allocation
                                ? 'bg-blue-100 border-blue-500 text-blue-800'
                                : cell.isCompatible
                                ? 'bg-green-50 border-green-300 hover:bg-green-100'
                                : 'bg-red-50 border-red-300'
                              }
                              ${cell.utilizationConflict ? 'border-yellow-400' : ''}
                              ${isResourceSelected && isTaskSelected ? 'ring-2 ring-purple-400' : ''}
                              ${isDragging && draggedItem?.id === task.id ? 'ring-2 ring-blue-400' : ''}
                            `}
                            onClick={() => handleCellClick(cell)}
                          >
                            {cell.allocation ? (
                              <div className="text-center">
                                <div className="font-medium">✓ Allocated</div>
                                <div className="text-xs opacity-75">
                                  {new Date(cell.allocation.startTime).toLocaleTimeString('en-US', { 
                                    hour: 'numeric', 
                                    minute: '2-digit',
                                    hour12: true 
                                  })}
                                </div>
                              </div>
                            ) : cell.isCompatible ? (
                              <div className="text-center">
                                <div>Click to allocate</div>
                                {cell.utilizationConflict && (
                                  <div className="text-yellow-600 text-xs mt-1">
                                    ⚠ High utilization
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="text-center text-red-600">
                                <div>✗ Incompatible</div>
                                <div className="text-xs">
                                  Missing skills
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Matrix Legend and Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <h3 className="font-medium mb-2">Selection Summary</h3>
          <div className="space-y-1 text-sm">
            <div>Resources selected: {selectedResources.length}</div>
            <div>Tasks selected: {selectedTasks.length}</div>
            <div>Compatible combinations: {
              matrixData.flat().filter(cell => 
                cell.isCompatible && 
                selectedResources.includes(cell.resourceId) && 
                cell.taskId && selectedTasks.includes(cell.taskId)
              ).length
            }</div>
          </div>
        </Card>
        
        <Card className="p-4">
          <h3 className="font-medium mb-2">Quick Actions</h3>
          <div className="space-y-2">
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full"
              disabled={createAllocationMutation.isPending}
            >
              Allocate All Compatible
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full"
              disabled={createAllocationMutation.isPending}
            >
              Clear All Allocations
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}

// Helper function to check if resource is compatible with task
function checkResourceTaskCompatibility(resource: any, task: any): boolean {
  // Check if resource type matches task requirements
  const resourceTypeMatch = true // Simplified - in real implementation, check task requirements
  
  // Check if resource has required skills
  const hasRequiredSkills = task.requiredSkills.every((requiredSkill: string) =>
    resource.skills.some((resourceSkill: string) => 
      resourceSkill.toLowerCase().includes(requiredSkill.toLowerCase())
    )
  )

  // Check if resource is available
  const isAvailable = resource.status === 'available'

  return resourceTypeMatch && hasRequiredSkills && isAvailable
}

// Helper function to check for utilization conflicts
function checkUtilizationConflict(resourceId: string, taskId: string, allocations: any[]): boolean {
  const resourceAllocations = allocations.filter(a => a.resourceId === resourceId)
  const totalUtilization = resourceAllocations.reduce((sum, allocation) => {
    return sum + (allocation.utilizationPercentage || 0)
  }, 0)
  
  // Consider it a conflict if adding this task would exceed 100% utilization
  return totalUtilization > 80 // Threshold for warning
}