// Re-export all scheduling-related types
export * from './jobs'
export * from './tasks'

// Re-export ScheduledTask from the canonical source to avoid duplication
export type { ScheduledTask } from '@/core/types/database'

// Scheduling preferences and view state types
export interface SchedulingViewState {
  currentView: 'gantt' | 'calendar' | 'list'
  selectedJobId: string | null
  selectedMachineId: string | null
  dateRange: {
    start: Date
    end: Date
  }
}

export interface SchedulingPreferences {
  showCompletedJobs: boolean
  groupByMachine: boolean
  timeGranularity: 15 | 30 | 60 // minutes
}