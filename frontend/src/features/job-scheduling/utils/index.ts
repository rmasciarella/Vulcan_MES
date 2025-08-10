// Job scheduling utilities
// Utility functions for job scheduling operations

import type { JobPriority } from '../../scheduling/types/jobs'

// Priority ordering for scheduling optimization
export const PRIORITY_ORDER: Record<JobPriority, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
}

// Sort jobs by priority
export function sortJobsByPriority<T extends { priority?: JobPriority }>(jobs: T[]): T[] {
  return [...jobs].sort((a, b) => {
    const aPriority = PRIORITY_ORDER[a.priority || 'medium']
    const bPriority = PRIORITY_ORDER[b.priority || 'medium']
    return bPriority - aPriority
  })
}

// Calculate job scheduling conflicts
export function calculateSchedulingConflicts(scheduledJobs: Array<{
  jobId: string
  scheduledStartDate?: Date
  scheduledEndDate?: Date
}>): Array<{
  jobId: string
  conflictType: 'time' | 'resource'
  description: string
}> {
  const conflicts: Array<{
    jobId: string
    conflictType: 'time' | 'resource'
    description: string
  }> = []

  for (let i = 0; i < scheduledJobs.length; i++) {
    for (let j = i + 1; j < scheduledJobs.length; j++) {
      const job1 = scheduledJobs[i]
      const job2 = scheduledJobs[j]
      
      if (job1 && job2 && job1.scheduledStartDate && job1.scheduledEndDate && 
          job2.scheduledStartDate && job2.scheduledEndDate) {
        
        const overlap = (job1.scheduledStartDate < job2.scheduledEndDate) &&
                        (job2.scheduledStartDate < job1.scheduledEndDate)
        
        if (overlap) {
          conflicts.push({
            jobId: job1.jobId,
            conflictType: 'time',
            description: `Time conflict with job ${job2.jobId}`,
          })
        }
      }
    }
  }

  return conflicts
}

// Format time duration for display
export function formatDuration(startDate: Date, endDate: Date): string {
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes}m`
  }
  return `${diffMinutes}m`
}

// Generate time slots for scheduling
export function generateTimeSlots(
  startDate: Date,
  endDate: Date,
  intervalMinutes: number = 60
): Date[] {
  const slots: Date[] = []
  const current = new Date(startDate)
  
  while (current <= endDate) {
    slots.push(new Date(current))
    current.setMinutes(current.getMinutes() + intervalMinutes)
  }
  
  return slots
}