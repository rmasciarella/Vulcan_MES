import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { Job, JobPriority } from '../../scheduling/types/jobs'

export interface JobSchedulingFilters {
  priority?: JobPriority
  search?: string
  dateRange?: {
    start: Date
    end: Date
  }
}

export interface JobSchedulingState {
  // Current view state
  currentView: 'timeline' | 'kanban' | 'list'
  selectedJobs: string[]
  filters: JobSchedulingFilters
  
  // Drag and drop state
  isDragging: boolean
  draggedJobId: string | null
  
  // Scheduling draft state
  schedulingDraft: {
    jobs: Array<{
      jobId: string
      scheduledStartDate?: Date
      scheduledEndDate?: Date
      priority?: JobPriority
    }>
    isDirty: boolean
  }

  // UI preferences
  preferences: {
    autoSchedule: boolean
    showDependencies: boolean
    groupByPriority: boolean
    timeScale: 'hours' | 'days' | 'weeks'
  }

  // Actions
  setView: (view: JobSchedulingState['currentView']) => void
  setFilters: (filters: Partial<JobSchedulingFilters>) => void
  toggleJobSelection: (jobId: string) => void
  selectAllJobs: (jobIds: string[]) => void
  clearSelection: () => void
  
  // Drag and drop actions
  startDragging: (jobId: string) => void
  stopDragging: () => void
  
  // Scheduling draft actions
  updateJobSchedule: (jobId: string, schedule: { 
    scheduledStartDate?: Date
    scheduledEndDate?: Date
    priority?: JobPriority
  }) => void
  removeJobFromSchedule: (jobId: string) => void
  clearSchedulingDraft: () => void
  
  // Preferences
  updatePreferences: (prefs: Partial<JobSchedulingState['preferences']>) => void
}

export const useJobSchedulingStore = create<JobSchedulingState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        currentView: 'timeline',
        selectedJobs: [],
        filters: {},
        isDragging: false,
        draggedJobId: null,
        schedulingDraft: {
          jobs: [],
          isDirty: false,
        },
        preferences: {
          autoSchedule: true,
          showDependencies: true,
          groupByPriority: false,
          timeScale: 'days',
        },

        // Actions
        setView: (view) => set({ currentView: view }),
        
        setFilters: (filters) =>
          set((state) => ({
            filters: { ...state.filters, ...filters },
          })),

        toggleJobSelection: (jobId) =>
          set((state) => ({
            selectedJobs: state.selectedJobs.includes(jobId)
              ? state.selectedJobs.filter((id) => id !== jobId)
              : [...state.selectedJobs, jobId],
          })),

        selectAllJobs: (jobIds) => set({ selectedJobs: jobIds }),
        clearSelection: () => set({ selectedJobs: [] }),

        // Drag and drop actions
        startDragging: (jobId) =>
          set({
            isDragging: true,
            draggedJobId: jobId,
          }),

        stopDragging: () =>
          set({
            isDragging: false,
            draggedJobId: null,
          }),

        // Scheduling draft actions
        updateJobSchedule: (jobId, schedule) =>
          set((state) => {
            const existingIndex = state.schedulingDraft.jobs.findIndex(
              (job) => job.jobId === jobId,
            )
            
            let updatedJobs
            if (existingIndex >= 0) {
              updatedJobs = state.schedulingDraft.jobs.map((job, index) =>
                index === existingIndex
                  ? { ...job, ...schedule }
                  : job,
              )
            } else {
              updatedJobs = [
                ...state.schedulingDraft.jobs,
                { jobId, ...schedule },
              ]
            }

            return {
              schedulingDraft: {
                jobs: updatedJobs,
                isDirty: true,
              },
            }
          }),

        removeJobFromSchedule: (jobId) =>
          set((state) => ({
            schedulingDraft: {
              jobs: state.schedulingDraft.jobs.filter((job) => job.jobId !== jobId),
              isDirty: state.schedulingDraft.jobs.some((job) => job.jobId === jobId),
            },
          })),

        clearSchedulingDraft: () =>
          set({
            schedulingDraft: { jobs: [], isDirty: false },
          }),

        updatePreferences: (prefs) =>
          set((state) => ({
            preferences: { ...state.preferences, ...prefs },
          })),
      }),
      {
        name: 'vulcan-job-scheduling-store',
        partialize: (state) => ({
          currentView: state.currentView,
          filters: state.filters,
          preferences: state.preferences,
        }),
      },
    ),
    {
      name: 'JobSchedulingStore',
    },
  ),
)