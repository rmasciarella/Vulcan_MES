import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

export interface ResourceAllocation {
  id: string
  resourceId: string
  resourceType: 'machine' | 'operator' | 'workcell'
  taskId: string
  jobId: string
  startTime: Date
  endTime: Date
  utilizationPercentage: number
  status: 'allocated' | 'available' | 'maintenance' | 'offline'
}

export interface ResourceFilters {
  resourceType?: 'machine' | 'operator' | 'workcell' | 'all'
  status?: 'allocated' | 'available' | 'maintenance' | 'offline' | 'all'
  utilizationMin?: number
  utilizationMax?: number
  dateRange?: {
    start: Date
    end: Date
  }
  search?: string
}

export interface ResourceAllocationState {
  // Current view state
  currentView: 'matrix' | 'timeline' | 'utilization' | 'capacity'
  selectedResources: string[]
  selectedTasks: string[]
  filters: ResourceFilters
  
  // Allocation state
  allocations: ResourceAllocation[]
  pendingAllocations: Array<{
    taskId: string
    jobId: string
    requiredResourceType: 'machine' | 'operator' | 'workcell'
    requiredSkills?: string[]
    estimatedDuration: number
    priority: number
  }>
  
  // Drag and drop state
  isDragging: boolean
  draggedItem: {
    type: 'task' | 'allocation'
    id: string
  } | null
  
  // Conflict detection
  conflicts: Array<{
    type: 'resource_overallocation' | 'skill_mismatch' | 'time_conflict'
    resourceId: string
    taskIds: string[]
    description: string
    severity: 'high' | 'medium' | 'low'
  }>

  // UI preferences
  preferences: {
    autoAllocate: boolean
    showConflicts: boolean
    groupByResourceType: boolean
    showUtilizationThreshold: number // percentage
    timeGranularity: 15 | 30 | 60 // minutes
  }

  // Actions
  setView: (view: ResourceAllocationState['currentView']) => void
  setFilters: (filters: Partial<ResourceFilters>) => void
  toggleResourceSelection: (resourceId: string) => void
  toggleTaskSelection: (taskId: string) => void
  selectAllResources: (resourceIds: string[]) => void
  selectAllTasks: (taskIds: string[]) => void
  clearResourceSelection: () => void
  clearTaskSelection: () => void
  
  // Drag and drop actions
  startDragging: (type: 'task' | 'allocation', id: string) => void
  stopDragging: () => void
  
  // Allocation management
  addAllocation: (allocation: Omit<ResourceAllocation, 'id'>) => void
  updateAllocation: (id: string, updates: Partial<ResourceAllocation>) => void
  removeAllocation: (id: string) => void
  addPendingAllocation: (allocation: ResourceAllocationState['pendingAllocations'][0]) => void
  removePendingAllocation: (taskId: string) => void
  
  // Conflict management
  updateConflicts: (conflicts: ResourceAllocationState['conflicts']) => void
  clearConflicts: () => void
  
  // Preferences
  updatePreferences: (prefs: Partial<ResourceAllocationState['preferences']>) => void
  
  // Reset state
  reset: () => void
}

export const useResourceAllocationStore = create<ResourceAllocationState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        currentView: 'matrix',
        selectedResources: [],
        selectedTasks: [],
        filters: {
          resourceType: 'all',
          status: 'all',
        },
        allocations: [],
        pendingAllocations: [],
        isDragging: false,
        draggedItem: null,
        conflicts: [],
        preferences: {
          autoAllocate: false,
          showConflicts: true,
          groupByResourceType: true,
          showUtilizationThreshold: 80,
          timeGranularity: 30,
        },

        // Actions
        setView: (view) => set({ currentView: view }),
        
        setFilters: (filters) =>
          set((state) => ({
            filters: { ...state.filters, ...filters },
          })),

        toggleResourceSelection: (resourceId) =>
          set((state) => ({
            selectedResources: state.selectedResources.includes(resourceId)
              ? state.selectedResources.filter((id) => id !== resourceId)
              : [...state.selectedResources, resourceId],
          })),

        toggleTaskSelection: (taskId) =>
          set((state) => ({
            selectedTasks: state.selectedTasks.includes(taskId)
              ? state.selectedTasks.filter((id) => id !== taskId)
              : [...state.selectedTasks, taskId],
          })),

        selectAllResources: (resourceIds) => set({ selectedResources: resourceIds }),
        selectAllTasks: (taskIds) => set({ selectedTasks: taskIds }),
        clearResourceSelection: () => set({ selectedResources: [] }),
        clearTaskSelection: () => set({ selectedTasks: [] }),

        // Drag and drop actions
        startDragging: (type, id) =>
          set({
            isDragging: true,
            draggedItem: { type, id },
          }),

        stopDragging: () =>
          set({
            isDragging: false,
            draggedItem: null,
          }),

        // Allocation management
        addAllocation: (allocation) => {
          const id = `alloc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
          set((state) => ({
            allocations: [...state.allocations, { ...allocation, id }],
          }))
        },

        updateAllocation: (id, updates) =>
          set((state) => ({
            allocations: state.allocations.map((allocation) =>
              allocation.id === id ? { ...allocation, ...updates } : allocation,
            ),
          })),

        removeAllocation: (id) =>
          set((state) => ({
            allocations: state.allocations.filter((allocation) => allocation.id !== id),
          })),

        addPendingAllocation: (allocation) =>
          set((state) => {
            // Remove existing pending allocation for the same task
            const filteredPending = state.pendingAllocations.filter(
              (pending) => pending.taskId !== allocation.taskId,
            )
            return {
              pendingAllocations: [...filteredPending, allocation],
            }
          }),

        removePendingAllocation: (taskId) =>
          set((state) => ({
            pendingAllocations: state.pendingAllocations.filter(
              (pending) => pending.taskId !== taskId,
            ),
          })),

        // Conflict management
        updateConflicts: (conflicts) => set({ conflicts }),
        clearConflicts: () => set({ conflicts: [] }),

        updatePreferences: (prefs) =>
          set((state) => ({
            preferences: { ...state.preferences, ...prefs },
          })),

        reset: () =>
          set({
            selectedResources: [],
            selectedTasks: [],
            allocations: [],
            pendingAllocations: [],
            isDragging: false,
            draggedItem: null,
            conflicts: [],
          }),
      }),
      {
        name: 'vulcan-resource-allocation-store',
        partialize: (state) => ({
          currentView: state.currentView,
          filters: state.filters,
          preferences: state.preferences,
        }),
      },
    ),
    {
      name: 'ResourceAllocationStore',
    },
  ),
)