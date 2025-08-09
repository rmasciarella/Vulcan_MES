// Re-export all scheduling-related types
export * from './jobs'
export * from './tasks'

// Additional scheduling types
export interface ScheduledTask {
  id: string
  jobId: string
  startTime: Date
  endTime: Date
  machineId?: string
  operatorId?: string
  status: 'scheduled' | 'in_progress' | 'completed'
}

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