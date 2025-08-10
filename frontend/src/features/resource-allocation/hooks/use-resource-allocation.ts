import { useCallback, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useResourceAllocationStore } from '../stores/resource-allocation-store'
import { useJobs, jobKeys } from '../../scheduling/hooks/use-jobs'
import { useMachines } from '../../scheduling/hooks/use-machines'
import { useOperators } from '../../scheduling/hooks/use-operators'
import { useUIStore } from '@/core/stores/ui-store'
import type { ResourceAllocation, ResourceFilters } from '../stores/resource-allocation-store'

// Main hook for resource allocation management
export function useResourceAllocation() {
  const {
    currentView,
    selectedResources,
    selectedTasks,
    filters,
    allocations,
    pendingAllocations,
    isDragging,
    draggedItem,
    conflicts,
    preferences,
    setView,
    setFilters,
    toggleResourceSelection,
    toggleTaskSelection,
    selectAllResources,
    selectAllTasks,
    clearResourceSelection,
    clearTaskSelection,
    startDragging,
    stopDragging,
    addAllocation,
    updateAllocation,
    removeAllocation,
    addPendingAllocation,
    removePendingAllocation,
    updateConflicts,
    clearConflicts,
    updatePreferences,
    reset,
  } = useResourceAllocationStore()

  return {
    // State
    currentView,
    selectedResources,
    selectedTasks,
    filters,
    allocations,
    pendingAllocations,
    isDragging,
    draggedItem,
    conflicts,
    preferences,
    
    // Actions
    setView,
    setFilters,
    toggleResourceSelection,
    toggleTaskSelection,
    selectAllResources,
    selectAllTasks,
    clearResourceSelection,
    clearTaskSelection,
    startDragging,
    stopDragging,
    addAllocation,
    updateAllocation,
    removeAllocation,
    addPendingAllocation,
    removePendingAllocation,
    updateConflicts,
    clearConflicts,
    updatePreferences,
    reset,
  }
}

// Hook for fetching and filtering resources
export function useResources() {
  const { filters } = useResourceAllocationStore()
  
  // Fetch different resource types
  const { data: machines, isLoading: machinesLoading } = useMachines()
  const { data: operators, isLoading: operatorsLoading } = useOperators()
  
  // In a real implementation, we would also fetch workcells
  // const { data: workcells, isLoading: workcellsLoading } = useWorkcells()

  const resources = useMemo(() => {
    const allResources = [
      ...(machines || []).map(machine => ({
        id: machine.id,
        name: machine.name,
        type: 'machine' as const,
        status: (machine.status || 'available') as 'allocated' | 'available' | 'maintenance' | 'offline',
        skills: [], // TODO: Add skills to machine schema
        utilization: 0, // TODO: Calculate utilization
      })),
      ...(operators || []).map(operator => ({
        id: operator.operator_id,
        name: `${operator.first_name} ${operator.last_name}`,
        type: 'operator' as const,
        status: (operator.status || 'available') as 'allocated' | 'available' | 'maintenance' | 'offline',
        skills: [], // TODO: Add skills to operator schema
        utilization: 0, // TODO: Calculate utilization
      })),
    ]

    // Apply filters
    let filteredResources = allResources

    if (filters.resourceType && filters.resourceType !== 'all') {
      filteredResources = filteredResources.filter(r => r.type === filters.resourceType)
    }

    if (filters.status && filters.status !== 'all') {
      filteredResources = filteredResources.filter(r => r.status === filters.status)
    }

    if (filters.utilizationMin !== undefined) {
      filteredResources = filteredResources.filter(r => r.utilization >= filters.utilizationMin!)
    }

    if (filters.utilizationMax !== undefined) {
      filteredResources = filteredResources.filter(r => r.utilization <= filters.utilizationMax!)
    }

    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      filteredResources = filteredResources.filter(r => 
        r.name.toLowerCase().includes(searchLower) ||
        r.skills.some(skill => skill.toLowerCase().includes(searchLower))
      )
    }

    return filteredResources
  }, [machines, operators, filters])

  return {
    resources,
    isLoading: machinesLoading || operatorsLoading,
    machines: machines || [],
    operators: operators || [],
  }
}

// Hook for available tasks that need resource allocation
export function useUnallocatedTasks() {
  const { data: jobs } = useJobs()
  const { allocations } = useResourceAllocationStore()

  const unallocatedTasks = useMemo(() => {
    if (!jobs) return []

    const allocatedTaskIds = new Set(allocations.map(a => a.taskId))
    
    return jobs.flatMap(job => 
      (job.tasks || [])
        .filter(task => !allocatedTaskIds.has(task.id))
        .map(task => ({
          id: task.id,
          name: task.name,
          jobId: job.id,
          jobName: job.name,
          requiredSkills: task.skills || [],
          estimatedDuration: task.estimatedDuration || 60, // Default 1 hour
          priority: job.priority === 'critical' ? 4 : 
                   job.priority === 'high' ? 3 : 
                   job.priority === 'medium' ? 2 : 1,
          status: task.status,
          isSetupTask: task.isSetupTask || false,
          sequence: task.sequence || 0,
        }))
    )
  }, [jobs, allocations])

  return unallocatedTasks
}

// Hook for creating resource allocations
export function useCreateAllocation() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)
  const { addAllocation, removePendingAllocation } = useResourceAllocationStore()

  return useMutation({
    mutationFn: async (allocationData: {
      resourceId: string
      resourceType: 'machine' | 'operator' | 'workcell'
      taskId: string
      jobId: string
      startTime: Date
      endTime: Date
    }) => {
      // In a real implementation, this would call the backend API
      await new Promise(resolve => setTimeout(resolve, 500))
      
      const allocation: Omit<ResourceAllocation, 'id'> = {
        ...allocationData,
        utilizationPercentage: 100, // Could be calculated based on task requirements
        status: 'allocated',
      }
      
      return allocation
    },
    onSuccess: (allocation, variables) => {
      // Add to local state
      addAllocation(allocation)
      
      // Remove from pending allocations if it was there
      removePendingAllocation(variables.taskId)
      
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['resources'] })
      queryClient.invalidateQueries({ queryKey: jobKeys.all })

      addNotification({
        type: 'success',
        title: 'Resource Allocated',
        message: `Task has been allocated to resource successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Allocation Failed',
        message: error.message || 'Failed to allocate resource',
      })
    },
  })
}

// Hook for batch resource allocation
export function useBatchAllocate() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)
  const { selectedTasks, selectedResources, clearTaskSelection, clearResourceSelection } = useResourceAllocationStore()

  return useMutation({
    mutationFn: async (allocationStrategy: 'auto' | 'manual') => {
      // In a real implementation, this would use the OR-Tools optimization service
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      return {
        allocatedCount: Math.min(selectedTasks.length, selectedResources.length),
        strategy: allocationStrategy,
      }
    },
    onSuccess: (result) => {
      // Clear selections after successful allocation
      clearTaskSelection()
      clearResourceSelection()
      
      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ['resources'] })
      queryClient.invalidateQueries({ queryKey: jobKeys.all })

      addNotification({
        type: 'success',
        title: 'Batch Allocation Complete',
        message: `${result.allocatedCount} tasks allocated using ${result.strategy} strategy`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Batch Allocation Failed',
        message: error.message || 'Failed to perform batch allocation',
      })
    },
  })
}

// Hook for optimizing resource allocation
export function useOptimizeAllocation() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (constraints: {
      optimizeFor: 'makespan' | 'utilization' | 'balance'
      timeHorizon: number // hours
      respectSkills: boolean
      allowReallocation: boolean
    }) => {
      // In a real implementation, this would call the optimization service
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      return {
        optimizedAllocations: [],
        improvementPercentage: 15,
        conflictsResolved: 5,
      }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['resources'] })
      queryClient.invalidateQueries({ queryKey: jobKeys.all })

      addNotification({
        type: 'success',
        title: 'Optimization Complete',
        message: `${result.improvementPercentage}% improvement achieved, ${result.conflictsResolved} conflicts resolved`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Optimization Failed',
        message: error.message || 'Failed to optimize resource allocation',
      })
    },
  })
}

// Hook for conflict detection and resolution
export function useResourceConflicts() {
  const { allocations, conflicts, updateConflicts } = useResourceAllocationStore()

  const detectConflicts = useCallback(() => {
    const detectedConflicts: typeof conflicts = []

    // Check for resource over-allocation (same resource, overlapping time)
    const resourceTimeSlots: Record<string, Array<{ start: Date; end: Date; taskId: string }>> = {}
    
    allocations.forEach(allocation => {
      if (!resourceTimeSlots[allocation.resourceId]) {
        resourceTimeSlots[allocation.resourceId] = []
      }
      resourceTimeSlots[allocation.resourceId].push({
        start: allocation.startTime,
        end: allocation.endTime,
        taskId: allocation.taskId,
      })
    })

    // Detect overlapping allocations
    Object.entries(resourceTimeSlots).forEach(([resourceId, slots]) => {
      for (let i = 0; i < slots.length; i++) {
        for (let j = i + 1; j < slots.length; j++) {
          const slot1 = slots[i]
          const slot2 = slots[j]
          
          const overlap = (slot1.start < slot2.end) && (slot2.start < slot1.end)
          
          if (overlap) {
            detectedConflicts.push({
              type: 'resource_overallocation',
              resourceId,
              taskIds: [slot1.taskId, slot2.taskId],
              description: `Resource ${resourceId} is over-allocated between ${slot1.start.toLocaleTimeString()} and ${slot2.end.toLocaleTimeString()}`,
              severity: 'high',
            })
          }
        }
      }
    })

    updateConflicts(detectedConflicts)
    return detectedConflicts
  }, [allocations, updateConflicts])

  return {
    conflicts,
    hasConflicts: conflicts.length > 0,
    detectConflicts,
  }
}

// Hook for resource utilization analytics
export function useResourceUtilization() {
  const { allocations, filters } = useResourceAllocationStore()
  const { resources } = useResources()

  const utilizationData = useMemo(() => {
    if (!filters.dateRange) return []

    const { start, end } = filters.dateRange
    const totalHours = (end.getTime() - start.getTime()) / (1000 * 60 * 60)

    return resources.map(resource => {
      const resourceAllocations = allocations.filter(a => a.resourceId === resource.id)
      
      const allocatedHours = resourceAllocations.reduce((total, allocation) => {
        const duration = (allocation.endTime.getTime() - allocation.startTime.getTime()) / (1000 * 60 * 60)
        return total + duration
      }, 0)

      const utilization = totalHours > 0 ? (allocatedHours / totalHours) * 100 : 0

      return {
        resourceId: resource.id,
        resourceName: resource.name,
        resourceType: resource.type,
        utilization,
        allocatedHours,
        availableHours: totalHours - allocatedHours,
        allocationCount: resourceAllocations.length,
      }
    })
  }, [allocations, resources, filters.dateRange])

  const overUtilizedResources = utilizationData.filter(
    data => data.utilization > (useResourceAllocationStore.getState().preferences.showUtilizationThreshold || 80)
  )

  const underUtilizedResources = utilizationData.filter(
    data => data.utilization < 50
  )

  return {
    utilizationData,
    overUtilizedResources,
    underUtilizedResources,
    averageUtilization: utilizationData.length > 0 
      ? utilizationData.reduce((sum, data) => sum + data.utilization, 0) / utilizationData.length 
      : 0,
  }
}