import { useQuery } from '@tanstack/react-query'
import type { ResourceCapacity, ResourceAllocation } from '../__tests__/test-utils/mock-resource-data'
import { generateMockResources, generateMockAllocations } from '../__tests__/test-utils/mock-resource-data'

// Resource query keys factory - following established pattern from use-jobs.ts
export const resourceKeys = {
  all: ['resources'] as const,
  lists: () => [...resourceKeys.all, 'list'] as const,
  capacities: () => [...resourceKeys.all, 'capacities'] as const,
  allocations: () => [...resourceKeys.all, 'allocations'] as const,
  byDepartment: (department: string) => [...resourceKeys.all, 'department', department] as const,
  byType: (type: 'machine' | 'operator' | 'workcell') => [...resourceKeys.all, 'type', type] as const,
}

// Fetch resource capacity data
// TODO: Replace with actual API calls when backend is ready
async function fetchResourceCapacities(): Promise<ResourceCapacity[]> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 500))
  return generateMockResources()
}

// Fetch resource allocation data
// TODO: Replace with actual API calls when backend is ready
async function fetchResourceAllocations(): Promise<ResourceAllocation[]> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 500))
  const resources = generateMockResources()
  return generateMockAllocations(resources)
}

/**
 * Hook for fetching resource capacity data
 */
export function useResourceCapacities() {
  return useQuery({
    queryKey: resourceKeys.capacities(),
    queryFn: fetchResourceCapacities,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook for fetching resource allocation data
 */
export function useResourceAllocations() {
  return useQuery({
    queryKey: resourceKeys.allocations(),
    queryFn: fetchResourceAllocations,
    staleTime: 2 * 60 * 1000, // 2 minutes - more frequent updates for allocations
  })
}

/**
 * Combined hook for resource matrix data
 */
export function useResourceMatrixData() {
  const resourcesQuery = useResourceCapacities()
  const allocationsQuery = useResourceAllocations()
  
  return {
    resources: resourcesQuery.data ?? [],
    allocations: allocationsQuery.data ?? [],
    isLoading: resourcesQuery.isLoading || allocationsQuery.isLoading,
    isError: resourcesQuery.isError || allocationsQuery.isError,
    error: resourcesQuery.error || allocationsQuery.error,
    refetch: () => {
      resourcesQuery.refetch()
      allocationsQuery.refetch()
    }
  }
}