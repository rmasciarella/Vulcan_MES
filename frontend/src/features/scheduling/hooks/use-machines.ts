import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Machine } from '@/core/types/database'
import { getNotificationService } from '@/core/services/notification-service'
import { 
  machinesAPI, 
  type MachinesListFilters, 
  type MachineAvailability 
} from '@/features/resources/api'

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

// API functions using the machinesAPI
async function fetchMachines(filters?: MachinesListFilters): Promise<Machine[]> {
  return machinesAPI.getMachines(filters)
}

async function fetchMachineById(id: string): Promise<Machine | null> {
  try {
    return await machinesAPI.getMachine(id)
  } catch (error) {
    if (error instanceof Error && error.message.includes('not found')) {
      return null
    }
    throw error
  }
}

async function fetchMachineAvailability(id: string, start: Date, end: Date): Promise<MachineAvailability[]> {
  return machinesAPI.getMachineAvailability(id, start, end)
}

async function updateMachineActiveStatus({ id, isActive }: { id: string; isActive: boolean }): Promise<Machine> {
  return machinesAPI.updateMachine(id, { is_active: isActive })
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
  const notificationService = getNotificationService()

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

      notificationService.addNotification({
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

      notificationService.addNotification({
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
    queryFn: () => machinesAPI.getMachinesByWorkCell(workCellId),
    enabled: !!workCellId,
    staleTime: 60 * 1000,
  })
}

export function useMachinesByType(machineType: string) {
  return useQuery({
    queryKey: machineKeys.byType(machineType),
    queryFn: () => machinesAPI.getMachinesByType(machineType),
    enabled: !!machineType,
    staleTime: 60 * 1000,
  })
}

export function useActiveMachines() {
  return useQuery({
    queryKey: machineKeys.active(),
    queryFn: () => machinesAPI.getActiveMachines(),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // Auto-refresh for production dashboard
  })
}

export function useAvailableMachines() {
  return useQuery({
    queryKey: machineKeys.available(),
    queryFn: () => machinesAPI.getAvailableMachines(),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000, // Auto-refresh for scheduling dashboard
  })
}

export function useMachineStats() {
  return useQuery({
    queryKey: machineKeys.stats(),
    queryFn: () => machinesAPI.getMachineStats(),
    staleTime: 5 * 60 * 1000, // 5 minutes for stats
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
  })
}

// Hook to create a new machine
export function useCreateMachine() {
  const queryClient = useQueryClient()
  const notificationService = getNotificationService()

  return useMutation({
    mutationFn: async (machineData: {
      name: string
      machineType: string
      workCellId?: string
      departmentId?: string
      serialNumber?: string
      description?: string
    }) => {
      return machinesAPI.createMachine({
        name: machineData.name,
        machine_type: machineData.machineType,
        ...(machineData.workCellId !== undefined && { work_cell_id: machineData.workCellId }),
        ...(machineData.departmentId !== undefined && { department_id: machineData.departmentId }),
        ...(machineData.serialNumber !== undefined && { serial_number: machineData.serialNumber }),
        ...(machineData.description !== undefined && { description: machineData.description }),
      })
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

      notificationService.addNotification({
        type: 'success',
        title: 'Machine Created',
        message: `Machine ${newMachine.name} has been created successfully`,
      })
    },
    onError: (error) => {
      notificationService.addNotification({
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
  const notificationService = getNotificationService()

  return useMutation({
    mutationFn: async (id: string) => {
      await machinesAPI.deleteMachine(id)
      return id
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

      notificationService.addNotification({
        type: 'success',
        title: 'Machine Deleted',
        message: 'Machine has been deleted successfully',
      })
    },
    onError: (error) => {
      notificationService.addNotification({
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
  const notificationService = getNotificationService()

  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Machine['status'] }) => {
      return machinesAPI.updateMachine(id, {
        ...(status !== undefined && status !== null && { status })
      })
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

      notificationService.addNotification({
        type: 'success',
        title: 'Machine Status Updated',
        message: `Machine ${data.name} status changed to ${data.status}`,
      })
    },
    onError: (error) => {
      notificationService.addNotification({
        type: 'error',
        title: 'Status Update Failed',
        message: error.message,
      })
    },
  })
}

// Re-export types for convenience
export type { MachinesListFilters, MachineAvailability } from '@/features/resources/api'
