import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Operator } from '@/core/types/database'
import { useUIStore } from '@/core/stores/ui-store'

// TODO: Temporarily simplified until operator use cases are properly migrated
type OperatorsListFilters = {
  departmentId?: string
  status?: string
  certificationId?: string
}

// Enhanced query keys factory for better caching strategy
export const operatorKeys = {
  all: ['operators'] as const,
  lists: () => [...operatorKeys.all, 'list'] as const,
  list: (filters: OperatorsListFilters) => [...operatorKeys.lists(), filters] as const,
  details: () => [...operatorKeys.all, 'detail'] as const,
  detail: (id: string) => [...operatorKeys.details(), id] as const,
  availability: (id: string, start: Date, end: Date) =>
    [...operatorKeys.detail(id), 'availability', { start, end }] as const,
  byDepartment: (departmentId: string) => [...operatorKeys.all, 'department', departmentId] as const,
  byCertification: (certificationId: string) => [...operatorKeys.all, 'certification', certificationId] as const,
  stats: () => [...operatorKeys.all, 'stats'] as const,
}

// TODO: Implement proper API calls - temporary stubs
async function fetchOperators(filters?: OperatorsListFilters): Promise<Operator[]> {
  console.warn('Operator API not implemented - returning empty array')
  return []
}

async function fetchOperatorById(id: string): Promise<Operator | null> {
  console.warn('Operator API not implemented - returning null')
  return null
}

async function fetchOperatorAvailability(id: string, start: Date, end: Date) {
  console.warn('Operator availability API not implemented - returning empty array')
  return []
}

async function fetchOperatorsByDepartment(departmentId: string): Promise<Operator[]> {
  console.warn('Operator by department API not implemented')
  return []
}

async function fetchOperatorsByCertification(certificationId: string): Promise<Operator[]> {
  console.warn('Operator by certification API not implemented')
  return []
}

async function fetchOperatorStats() {
  console.warn('Operator stats API not implemented')
  return { count: 0, active: 0, available: 0 }
}

async function updateOperatorStatus({ id, status }: { id: string; status: Operator['status'] }): Promise<Operator> {
  console.warn('Update operator status API not implemented')
  throw new Error('Operator API not implemented')
}

async function updateOperatorActiveStatus({ id, isActive }: { id: string; isActive: boolean }): Promise<Operator> {
  console.warn('Update operator active status API not implemented')
  throw new Error('Operator API not implemented')
}

// Enhanced hook to fetch operators list
export function useOperators(filters?: OperatorsListFilters) {
  return useQuery({
    queryKey: operatorKeys.list(filters || {}),
    queryFn: () => fetchOperators(filters),
    staleTime: 60 * 1000, // 1 minute - shift changes need to be reflected quickly
  })
}

// Hook to fetch single operator
export function useOperator(id: string) {
  return useQuery({
    queryKey: operatorKeys.detail(id),
    queryFn: () => fetchOperatorById(id),
    enabled: !!id,
  })
}

// Hook to fetch operator availability
export function useOperatorAvailability(id: string, start: Date, end: Date) {
  return useQuery({
    queryKey: operatorKeys.availability(id, start, end),
    queryFn: () => fetchOperatorAvailability(id, start, end),
    enabled: !!id,
    staleTime: 30 * 1000, // 30 seconds - availability changes with scheduling
  })
}

// Hook to update operator status with optimistic updates
export function useUpdateOperatorStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: updateOperatorStatus,
    onMutate: async ({ id, status }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: operatorKeys.detail(id) })

      // Snapshot the previous value
      const previousOperator = queryClient.getQueryData(operatorKeys.detail(id))

      // Optimistically update the operator status
      if (previousOperator) {
        queryClient.setQueryData(operatorKeys.detail(id), {
          ...previousOperator,
          status,
          updated_at: new Date().toISOString(),
        })
      }

      return { previousOperator }
    },
    onSuccess: (data) => {
      // Update the specific operator in cache with server response
      queryClient.setQueryData(operatorKeys.detail(data.operator_id), data)

      // Only invalidate queries that depend on status
      queryClient.invalidateQueries({ queryKey: operatorKeys.lists() })
      queryClient.invalidateQueries({ queryKey: operatorKeys.stats() })
      
      // Invalidate department-specific queries if operator has department
      if (data.department_id) {
        queryClient.invalidateQueries({ queryKey: operatorKeys.byDepartment(data.department_id) })
      }

      addNotification({
        type: 'success',
        title: 'Operator Updated',
        message: `${data.first_name} ${data.last_name} status changed to ${data.status}`,
      })
    },
    onError: (error, { id }, context) => {
      // Rollback optimistic update
      if (context?.previousOperator) {
        queryClient.setQueryData(operatorKeys.detail(id), context.previousOperator)
      }

      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.message,
      })
    },
    onSettled: (_, __, { id }) => {
      // Always refetch after mutation to ensure consistency
      queryClient.invalidateQueries({ queryKey: operatorKeys.detail(id) })
    },
  })
}

// Hook to update operator active status
export function useUpdateOperatorActiveStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: updateOperatorActiveStatus,
    onSuccess: (data) => {
      // Update the specific operator in cache
      queryClient.setQueryData(operatorKeys.detail(data.operator_id), data)

      // Only invalidate queries affected by active status changes
      queryClient.invalidateQueries({ queryKey: operatorKeys.lists() })
      queryClient.invalidateQueries({ queryKey: operatorKeys.stats() })
      
      // Invalidate department-specific queries if operator has department
      if (data.department_id) {
        queryClient.invalidateQueries({ queryKey: operatorKeys.byDepartment(data.department_id) })
      }

      addNotification({
        type: 'success',
        title: 'Operator Updated',
        message: `${data.first_name} ${data.last_name} is now ${data.is_active ? 'active' : 'inactive'}`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.message,
      })
    },
  })
}

// Hook to create a new operator
export function useCreateOperator() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (data: {
      firstName: string
      lastName: string
      employeeId: string
      departmentId?: string
      email?: string
      phoneNumber?: string
    }) => {
      console.warn('Create operator API not implemented')
      throw new Error('Operator API not implemented')
    },
    onSuccess: (newOperator) => {
      // Add to cache and invalidate lists
      queryClient.setQueryData(operatorKeys.detail(newOperator.operator_id), newOperator)
      queryClient.invalidateQueries({ queryKey: operatorKeys.lists() })
      queryClient.invalidateQueries({ queryKey: operatorKeys.stats() })
      
      // Invalidate department-specific queries if operator has department
      if (newOperator.department_id) {
        queryClient.invalidateQueries({ queryKey: operatorKeys.byDepartment(newOperator.department_id) })
      }

      addNotification({
        type: 'success',
        title: 'Operator Created',
        message: `${newOperator.first_name} ${newOperator.last_name} has been created successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Create Operator Failed',
        message: error.message,
      })
    },
  })
}

// Hook to delete an operator
export function useDeleteOperator() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (id: string) => {
      console.warn('Delete operator API not implemented')
      throw new Error('Operator API not implemented')
    },
    onSuccess: (_, deletedId) => {
      // Get operator data before removing to optimize invalidations
      const deletedOperator = queryClient.getQueryData(operatorKeys.detail(deletedId)) as Operator | undefined
      
      // Remove from cache
      queryClient.removeQueries({ queryKey: operatorKeys.detail(deletedId) })
      queryClient.invalidateQueries({ queryKey: operatorKeys.lists() })
      queryClient.invalidateQueries({ queryKey: operatorKeys.stats() })

      // Only invalidate department-specific queries if we know the department
      if (deletedOperator?.department_id) {
        queryClient.invalidateQueries({ queryKey: operatorKeys.byDepartment(deletedOperator.department_id) })
      }

      addNotification({
        type: 'success',
        title: 'Operator Deleted',
        message: 'Operator has been deleted successfully',
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Operator Failed',
        message: error.message,
      })
    },
  })
}

// Specialized hooks for dashboard components
export function useOperatorsByDepartment(departmentId: string) {
  return useQuery({
    queryKey: operatorKeys.byDepartment(departmentId),
    queryFn: () => fetchOperatorsByDepartment(departmentId),
    enabled: !!departmentId,
    staleTime: 60 * 1000,
  })
}

export function useOperatorsByCertification(certificationId: string) {
  return useQuery({
    queryKey: operatorKeys.byCertification(certificationId),
    queryFn: () => fetchOperatorsByCertification(certificationId),
    enabled: !!certificationId,
    staleTime: 60 * 1000,
  })
}

export function useOperatorStats() {
  return useQuery({
    queryKey: operatorKeys.stats(),
    queryFn: fetchOperatorStats,
    staleTime: 5 * 60 * 1000, // 5 minutes for stats
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
  })
}

// Export types for external use
export type { OperatorsListFilters }
