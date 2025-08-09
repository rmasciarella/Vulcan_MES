import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Machine } from '@/core/types/database'
import { useUIStore } from '@/core/stores/ui-store'

// TODO: Temporarily simplified until machine use cases are properly migrated
// Machine functionality needs to be implemented in features/resources or scheduling
type MachinesListFilters = {
  status?: string
  type?: string
  workCellId?: string
}

type MachineAvailability = {
  id: string
  start: Date
  end: Date
  available: boolean
}

// Enhanced query keys factory for better caching strategy
export const machineKeys = {
  all: ['machines'] as const,
  lists: () => [...machineKeys.all, 'list'] as const,
  list: (filters: MachinesListFilters) => [...machineKeys.lists(), filters] as const,
  details: () => [...machineKeys.all, 'detail'] as const,
  detail: (id: string) => [...machineKeys.details(), id] as const,
  availability: (id: string, start: Date, end: Date) =>
    [...machineKeys.detail(id), 'availability', { start, end }] as const,
  byWorkCell: (workCellId: string) => [...machineKeys.all, 'workcell', workCellId] as const,
  byType: (machineType: string) => [...machineKeys.all, 'type', machineType] as const,
  active: () => [...machineKeys.all, 'active'] as const,
  available: () => [...machineKeys.all, 'available'] as const,
  stats: () => [...machineKeys.all, 'stats'] as const,
}

// TODO: Implement proper API calls
// These are temporary stubs until machine use cases are properly migrated
async function fetchMachines(filters?: MachinesListFilters): Promise<Machine[]> {
  // Temporary stub - implement proper API call
  console.warn('Machine API not implemented - returning empty array')
  return []
}

async function fetchMachineById(id: string): Promise<Machine | null> {
  // Temporary stub - implement proper API call
  console.warn('Machine API not implemented - returning null')
  return null
}

async function fetchMachineAvailability(id: string, start: Date, end: Date): Promise<MachineAvailability[]> {
  // Temporary stub - implement proper API call
  console.warn('Machine availability API not implemented - returning empty array')
  return []
}

async function updateMachineActiveStatus({ id, isActive }: { id: string; isActive: boolean }): Promise<Machine> {
  // Temporary stub - implement proper API call
  console.warn('Machine update API not implemented')
  throw new Error('Machine API not implemented')
}

// Enhanced hook to fetch machines list with comprehensive filtering
export function useMachines(
  filters?: MachinesListFilters,
  options?: {
    enableRealtime?: boolean
    refetchInterval?: number
    staleTime?: number
  }
) {
  const {
    enableRealtime = false,
    refetchInterval = enableRealtime ? 30 * 1000 : (false as const),
    staleTime = 30 * 1000,
  } = options || {}

  return useQuery({
    queryKey: machineKeys.list(filters || {}),
    queryFn: () => fetchMachines(filters),
    staleTime,
    refetchInterval,
    refetchIntervalInBackground: enableRealtime,
  })
}

// Hook to fetch single machine
export function useMachine(id: string) {
  return useQuery({
    queryKey: machineKeys.detail(id),
    queryFn: () => fetchMachineById(id),
    enabled: !!id,
  })
}

// Hook to fetch machine availability
export function useMachineAvailability(id: string, start: Date, end: Date) {
  return useQuery({
    queryKey: machineKeys.availability(id, start, end),
    queryFn: () => fetchMachineAvailability(id, start, end),
    enabled: !!id,
    staleTime: 30 * 1000, // 30 seconds
  })
}

// Enhanced hook to update machine active status with optimistic updates
export function useUpdateMachineActiveStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: updateMachineActiveStatus,
    onMutate: async ({ id, isActive }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: machineKeys.detail(id) })

      // Snapshot the previous value
      const previousMachine = queryClient.getQueryData(machineKeys.detail(id))

      // Optimistically update the machine status
      if (previousMachine) {
        queryClient.setQueryData(machineKeys.detail(id), {
          ...(previousMachine as Machine),
          is_active: isActive,
          updated_at: new Date().toISOString(),
        })
      }

      return { previousMachine }
    },
    onSuccess: (data) => {
      // Update the specific machine in cache with server response
      queryClient.setQueryData(machineKeys.detail(data.id), data)

      // Only invalidate queries that actually depend on active status
      queryClient.invalidateQueries({ queryKey: machineKeys.lists() })
      queryClient.invalidateQueries({ queryKey: machineKeys.active() })
      queryClient.invalidateQueries({ queryKey: machineKeys.available() })
      queryClient.invalidateQueries({ queryKey: machineKeys.stats() })

      addNotification({
        type: 'success',
        title: 'Machine Updated',
        message: `Machine ${data.name} is now ${data.is_active ? 'active' : 'inactive'}`,
      })
    },
    onError: (error, { id }, context) => {
      // Rollback optimistic update
      if (context?.previousMachine) {
        queryClient.setQueryData(machineKeys.detail(id), context.previousMachine)
      }

      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.message,
      })
    },
    onSettled: (_, __, { id }) => {
      // Always refetch after mutation to ensure consistency
      queryClient.invalidateQueries({ queryKey: machineKeys.detail(id) })
    },
  })
}

// Specialized hooks for common machine queries
export function useMachinesByWorkCell(workCellId: string) {
  return useQuery({
    queryKey: machineKeys.byWorkCell(workCellId),
    queryFn: async () => {
      // TODO: Implement proper API call
      console.warn('Machine by work cell API not implemented')
      return []
    },
    enabled: !!workCellId,
    staleTime: 60 * 1000,
  })
}

export function useMachinesByType(machineType: string) {
  return useQuery({
    queryKey: machineKeys.byType(machineType),
    queryFn: async () => {
      // TODO: Implement proper API call
      console.warn('Machine by type API not implemented')
      return []
    },
    enabled: !!machineType,
    staleTime: 60 * 1000,
  })
}

export function useActiveMachines() {
  return useQuery({
    queryKey: machineKeys.active(),
    queryFn: async () => {
      // TODO: Implement proper API call
      console.warn('Active machines API not implemented')
      return []
    },
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // Auto-refresh for production dashboard
  })
}

export function useAvailableMachines() {
  return useQuery({
    queryKey: machineKeys.available(),
    queryFn: async () => {
      // TODO: Implement proper API call
      console.warn('Available machines API not implemented')
      return []
    },
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // Auto-refresh for scheduling dashboard
  })
}

export function useMachineStats() {
  return useQuery({
    queryKey: machineKeys.stats(),
    queryFn: async () => {
      // TODO: Implement proper API call
      console.warn('Machine stats API not implemented')
      return { count: 0, active: 0, available: 0 }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes for stats
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
  })
}

// Hook to create a new machine
export function useCreateMachine() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (machineData: {
      name: string
      machineType: string
      workCellId?: string
      departmentId?: string
      serialNumber?: string
      description?: string
    }) => {
      // TODO: Implement proper API call
      console.warn('Create machine API not implemented')
      throw new Error('Machine API not implemented')
    },
    onSuccess: (newMachine) => {
      // Add to cache and invalidate lists
      queryClient.setQueryData(machineKeys.detail(newMachine.id), newMachine)
      queryClient.invalidateQueries({ queryKey: machineKeys.lists() })
      queryClient.invalidateQueries({ queryKey: machineKeys.stats() })
      
      // Only invalidate active if machine is created as active
      if (newMachine.is_active) {
        queryClient.invalidateQueries({ queryKey: machineKeys.active() })
        queryClient.invalidateQueries({ queryKey: machineKeys.available() })
      }

      // Invalidate related specific queries if applicable
      if (newMachine.work_cell_id) {
        queryClient.invalidateQueries({ queryKey: machineKeys.byWorkCell(newMachine.work_cell_id) })
      }
      if (newMachine.machine_type) {
        queryClient.invalidateQueries({ queryKey: machineKeys.byType(newMachine.machine_type) })
      }

      addNotification({
        type: 'success',
        title: 'Machine Created',
        message: `Machine ${newMachine.name} has been created successfully`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Create Machine Failed',
        message: error.message,
      })
    },
  })
}

// Hook to delete a machine
export function useDeleteMachine() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async (id: string) => {
      // TODO: Implement proper API call
      console.warn('Delete machine API not implemented')
      throw new Error('Machine API not implemented')
    },
    onSuccess: (_, deletedId) => {
      // Get machine data before removing to optimize invalidations
      const deletedMachine = queryClient.getQueryData(machineKeys.detail(deletedId)) as Machine | undefined
      
      // Remove from cache
      queryClient.removeQueries({ queryKey: machineKeys.detail(deletedId) })
      queryClient.invalidateQueries({ queryKey: machineKeys.lists() })
      queryClient.invalidateQueries({ queryKey: machineKeys.stats() })

      // Only invalidate specific queries if we had machine data
      if (deletedMachine) {
        if (deletedMachine.is_active) {
          queryClient.invalidateQueries({ queryKey: machineKeys.active() })
          queryClient.invalidateQueries({ queryKey: machineKeys.available() })
        }
        if (deletedMachine.work_cell_id) {
          queryClient.invalidateQueries({ queryKey: machineKeys.byWorkCell(deletedMachine.work_cell_id) })
        }
        if (deletedMachine.machine_type) {
          queryClient.invalidateQueries({ queryKey: machineKeys.byType(deletedMachine.machine_type) })
        }
      } else {
        // If we don't have the machine data, invalidate potentially affected queries
        queryClient.invalidateQueries({ queryKey: machineKeys.active() })
        queryClient.invalidateQueries({ queryKey: machineKeys.available() })
      }

      addNotification({
        type: 'success',
        title: 'Machine Deleted',
        message: 'Machine has been deleted successfully',
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Machine Failed',
        message: error.message,
      })
    },
  })
}

// Hook to update machine status
export function useUpdateMachineStatus() {
  const queryClient = useQueryClient()
  const addNotification = useUIStore((state) => state.addNotification)

  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Machine['status'] }) => {
      // TODO: Implement proper API call
      console.warn('Update machine status API not implemented')
      throw new Error('Machine API not implemented')
    },
    onSuccess: (data) => {
      // Update the specific machine in cache
      queryClient.setQueryData(machineKeys.detail(data.id), data)

      // Only invalidate queries affected by status changes
      queryClient.invalidateQueries({ queryKey: machineKeys.lists() })
      queryClient.invalidateQueries({ queryKey: machineKeys.stats() })
      
      // Status change affects availability
      queryClient.invalidateQueries({ queryKey: machineKeys.available() })
      
      // If machine becomes active/inactive, update active queries
      if (data.status === 'active' || data.status === 'inactive') {
        queryClient.invalidateQueries({ queryKey: machineKeys.active() })
      }

      addNotification({
        type: 'success',
        title: 'Machine Status Updated',
        message: `Machine ${data.name} status changed to ${data.status}`,
      })
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Status Update Failed',
        message: error.message,
      })
    },
  })
}

// Export types for external use
export type { MachinesListFilters, MachineAvailability }
