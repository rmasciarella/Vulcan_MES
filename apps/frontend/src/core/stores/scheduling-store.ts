import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { ScheduledTask } from '@/core/types/database'

interface SchedulingState {
  // Current view state
  currentView: 'gantt' | 'calendar' | 'list'
  selectedJobId: string | null
  selectedMachineId: string | null
  dateRange: {
    start: Date
    end: Date
  }

  // Temporary scheduling data (before saving)
  draftSchedule: {
    tasks: ScheduledTask[]
    isDirty: boolean
  }

  // UI preferences
  preferences: {
    showCompletedJobs: boolean
    groupByMachine: boolean
    timeGranularity: 15 | 30 | 60 // minutes
  }

  // Actions
  setView: (view: SchedulingState['currentView']) => void
  selectJob: (jobId: string | null) => void
  selectMachine: (machineId: string | null) => void
  setDateRange: (start: Date, end: Date) => void

  // Draft schedule actions
  addDraftTask: (task: ScheduledTask) => void
  updateDraftTask: (taskId: string, updates: Partial<ScheduledTask>) => void
  removeDraftTask: (taskId: string) => void
  clearDraftSchedule: () => void

  // Preferences
  updatePreferences: (prefs: Partial<SchedulingState['preferences']>) => void
}

export const useSchedulingStore = create<SchedulingState>()(
  devtools(
    persist(
      (set) => ({
        // Initial state
        currentView: 'gantt',
        selectedJobId: null,
        selectedMachineId: null,
        dateRange: {
          start: new Date(),
          end: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 1 week
        },
        draftSchedule: {
          tasks: [],
          isDirty: false,
        },
        preferences: {
          showCompletedJobs: false,
          groupByMachine: true,
          timeGranularity: 30,
        },

        // Actions
        setView: (view) => set({ currentView: view }),
        selectJob: (jobId) => set({ selectedJobId: jobId }),
        selectMachine: (machineId) => set({ selectedMachineId: machineId }),
        setDateRange: (start, end) =>
          set({
            dateRange: { start, end },
          }),

        // Draft schedule actions
        addDraftTask: (task) =>
          set((state) => ({
            draftSchedule: {
              tasks: [...state.draftSchedule.tasks, task],
              isDirty: true,
            },
          })),

        updateDraftTask: (taskId, updates) =>
          set((state) => ({
            draftSchedule: {
              tasks: state.draftSchedule.tasks.map((task) =>
                task.id === taskId ? { ...task, ...updates } : task,
              ),
              isDirty: true,
            },
          })),

        removeDraftTask: (taskId) =>
          set((state) => ({
            draftSchedule: {
              tasks: state.draftSchedule.tasks.filter((task) => task.id !== taskId),
              isDirty: true,
            },
          })),

        clearDraftSchedule: () =>
          set({
            draftSchedule: { tasks: [], isDirty: false },
          }),

        updatePreferences: (prefs) =>
          set((state) => ({
            preferences: { ...state.preferences, ...prefs },
          })),
      }),
      {
        name: 'vulcan-scheduling-store',
        partialize: (state) => ({
          currentView: state.currentView,
          dateRange: state.dateRange,
          preferences: state.preferences,
        }),
      },
    ),
    {
      name: 'SchedulingStore',
    },
  ),
)
