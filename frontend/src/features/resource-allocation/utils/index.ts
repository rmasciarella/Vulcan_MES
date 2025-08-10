// Resource allocation utilities
// Utility functions for resource allocation operations

import type { ResourceAllocation } from '../stores/resource-allocation-store'

// Calculate resource utilization percentage
export function calculateResourceUtilization(
  allocations: ResourceAllocation[],
  resourceId: string,
  timeWindow: { start: Date; end: Date }
): number {
  const resourceAllocations = allocations.filter(a => a.resourceId === resourceId)
  
  const totalWindowTime = timeWindow.end.getTime() - timeWindow.start.getTime()
  
  const allocatedTime = resourceAllocations.reduce((total, allocation) => {
    // Calculate overlap with time window
    const allocStart = Math.max(allocation.startTime.getTime(), timeWindow.start.getTime())
    const allocEnd = Math.min(allocation.endTime.getTime(), timeWindow.end.getTime())
    
    if (allocStart < allocEnd) {
      return total + (allocEnd - allocStart)
    }
    return total
  }, 0)
  
  return totalWindowTime > 0 ? (allocatedTime / totalWindowTime) * 100 : 0
}

// Check if two time periods overlap
export function timePeriodsOverlap(
  period1: { start: Date; end: Date },
  period2: { start: Date; end: Date }
): boolean {
  return period1.start < period2.end && period2.start < period1.end
}

// Find allocation conflicts for a resource
export function findResourceConflicts(
  allocations: ResourceAllocation[],
  resourceId: string
): Array<{
  conflictingAllocations: ResourceAllocation[]
  overlapStart: Date
  overlapEnd: Date
}> {
  const resourceAllocations = allocations.filter(a => a.resourceId === resourceId)
  const conflicts: Array<{
    conflictingAllocations: ResourceAllocation[]
    overlapStart: Date
    overlapEnd: Date
  }> = []
  
  for (let i = 0; i < resourceAllocations.length; i++) {
    for (let j = i + 1; j < resourceAllocations.length; j++) {
      const alloc1 = resourceAllocations[i]
      const alloc2 = resourceAllocations[j]
      
      if (timePeriodsOverlap(
        { start: alloc1.startTime, end: alloc1.endTime },
        { start: alloc2.startTime, end: alloc2.endTime }
      )) {
        const overlapStart = new Date(Math.max(alloc1.startTime.getTime(), alloc2.startTime.getTime()))
        const overlapEnd = new Date(Math.min(alloc1.endTime.getTime(), alloc2.endTime.getTime()))
        
        conflicts.push({
          conflictingAllocations: [alloc1, alloc2],
          overlapStart,
          overlapEnd,
        })
      }
    }
  }
  
  return conflicts
}

// Calculate optimal allocation score based on multiple factors
export function calculateAllocationScore(
  resource: any,
  task: any,
  existingAllocations: ResourceAllocation[]
): number {
  let score = 0
  
  // Base compatibility score
  if (checkResourceTaskCompatibility(resource, task)) {
    score += 50
  } else {
    return 0 // Incompatible allocation
  }
  
  // Skill match bonus
  const matchedSkills = task.requiredSkills?.filter((skill: string) =>
    resource.skills?.some((rSkill: string) => 
      rSkill.toLowerCase().includes(skill.toLowerCase())
    )
  ).length || 0
  const totalRequiredSkills = task.requiredSkills?.length || 1
  score += (matchedSkills / totalRequiredSkills) * 30
  
  // Utilization penalty (prefer less utilized resources)
  const currentUtilization = resource.utilization || 0
  score += (100 - currentUtilization) * 0.2
  
  // Priority bonus
  score += (task.priority || 1) * 5
  
  return Math.min(score, 100) // Cap at 100
}

// Check resource-task compatibility
export function checkResourceTaskCompatibility(resource: any, task: any): boolean {
  // Check if resource is available
  if (resource.status !== 'available') {
    return false
  }
  
  // Check if resource has required skills
  if (task.requiredSkills && task.requiredSkills.length > 0) {
    const hasAllSkills = task.requiredSkills.every((requiredSkill: string) =>
      resource.skills?.some((resourceSkill: string) => 
        resourceSkill.toLowerCase().includes(requiredSkill.toLowerCase())
      )
    )
    if (!hasAllSkills) {
      return false
    }
  }
  
  // Additional compatibility checks could be added here
  // (e.g., resource type matching, capacity constraints, etc.)
  
  return true
}

// Generate allocation suggestions using simple heuristics
export function generateAllocationSuggestions(
  resources: any[],
  tasks: any[],
  existingAllocations: ResourceAllocation[],
  strategy: 'balanced' | 'priority_first' | 'utilization_first' = 'balanced'
): Array<{
  resourceId: string
  taskId: string
  score: number
  reasoning: string
}> {
  const suggestions: Array<{
    resourceId: string
    taskId: string
    score: number
    reasoning: string
  }> = []
  
  // Sort tasks based on strategy
  const sortedTasks = [...tasks].sort((a, b) => {
    switch (strategy) {
      case 'priority_first':
        return (b.priority || 0) - (a.priority || 0)
      case 'utilization_first':
        return a.estimatedDuration - b.estimatedDuration
      default:
        return (b.priority || 0) * 0.6 + (a.estimatedDuration || 0) * 0.4 - 
               ((a.priority || 0) * 0.6 + (b.estimatedDuration || 0) * 0.4)
    }
  })
  
  sortedTasks.forEach(task => {
    const compatibleResources = resources.filter(resource => 
      checkResourceTaskCompatibility(resource, task)
    )
    
    if (compatibleResources.length === 0) {
      return // No compatible resources for this task
    }
    
    // Find best resource for this task
    const resourceScores = compatibleResources.map(resource => ({
      resource,
      score: calculateAllocationScore(resource, task, existingAllocations)
    }))
    
    const bestMatch = resourceScores.reduce((best, current) => 
      current.score > best.score ? current : best
    )
    
    if (bestMatch.score > 60) { // Only suggest if score is reasonably high
      suggestions.push({
        resourceId: bestMatch.resource.id,
        taskId: task.id,
        score: bestMatch.score,
        reasoning: generateReasoningText(bestMatch.resource, task, bestMatch.score)
      })
    }
  })
  
  return suggestions.sort((a, b) => b.score - a.score)
}

// Generate human-readable reasoning for allocation suggestion
function generateReasoningText(resource: any, task: any, score: number): string {
  const reasons: string[] = []
  
  if (score > 90) {
    reasons.push('Excellent match')
  } else if (score > 75) {
    reasons.push('Good match')
  } else {
    reasons.push('Acceptable match')
  }
  
  if (resource.utilization < 50) {
    reasons.push('low utilization')
  } else if (resource.utilization < 80) {
    reasons.push('moderate utilization')
  }
  
  const matchedSkills = task.requiredSkills?.filter((skill: string) =>
    resource.skills?.some((rSkill: string) => 
      rSkill.toLowerCase().includes(skill.toLowerCase())
    )
  ).length || 0
  
  if (matchedSkills === task.requiredSkills?.length) {
    reasons.push('perfect skill match')
  } else if (matchedSkills > 0) {
    reasons.push('partial skill match')
  }
  
  return reasons.join(', ')
}

// Format allocation duration for display
export function formatAllocationDuration(startTime: Date, endTime: Date): string {
  const durationMs = endTime.getTime() - startTime.getTime()
  const hours = Math.floor(durationMs / (1000 * 60 * 60))
  const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

// Group allocations by time period
export function groupAllocationsByTimePeriod(
  allocations: ResourceAllocation[],
  periodType: 'hour' | 'day' | 'week'
): Record<string, ResourceAllocation[]> {
  return allocations.reduce((groups, allocation) => {
    let key: string
    
    switch (periodType) {
      case 'hour':
        key = allocation.startTime.toISOString().slice(0, 13) // YYYY-MM-DDTHH
        break
      case 'day':
        key = allocation.startTime.toISOString().slice(0, 10) // YYYY-MM-DD
        break
      case 'week':
        const weekStart = new Date(allocation.startTime)
        weekStart.setDate(weekStart.getDate() - weekStart.getDay())
        key = weekStart.toISOString().slice(0, 10)
        break
      default:
        key = allocation.startTime.toISOString().slice(0, 10)
    }
    
    if (!groups[key]) {
      groups[key] = []
    }
    groups[key].push(allocation)
    
    return groups
  }, {} as Record<string, ResourceAllocation[]>)
}