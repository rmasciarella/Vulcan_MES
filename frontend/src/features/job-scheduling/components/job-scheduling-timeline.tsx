import React, { useMemo } from 'react'
import { Card } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { useJobScheduling, useJobSchedulingPreferences } from '../hooks/use-job-scheduling'

export function JobSchedulingTimeline({ jobs }: { jobs: any[] }) {
  const { 
    selectedJobs, 
    schedulingDraft,
    toggleJobSelection,
    updateJobSchedule,
    startDragging,
    stopDragging,
    isDragging,
    draggedJobId 
  } = useJobScheduling()
  
  const { preferences } = useJobSchedulingPreferences()

  // Generate timeline data based on time scale and date range
  const timelineData = useMemo(() => {
    const now = new Date()
    const timeSlots: Date[] = []
    
    // Generate time slots based on preferences
    const { timeScale } = preferences
    const hoursToAdd = timeScale === 'hours' ? 1 : timeScale === 'days' ? 24 : 168 // 168 hours = 1 week
    
    for (let i = 0; i < 14; i++) {
      const slot = new Date(now.getTime() + (i * hoursToAdd * 60 * 60 * 1000))
      timeSlots.push(slot)
    }
    
    return timeSlots
  }, [preferences.timeScale])

  const handleJobDrop = (jobId: string, timeSlot: Date) => {
    if (!isDragging || draggedJobId !== jobId) return
    
    // Calculate end time based on estimated duration (placeholder logic)
    const endTime = new Date(timeSlot.getTime() + (4 * 60 * 60 * 1000)) // 4 hours default
    
    updateJobSchedule(jobId, {
      scheduledStartDate: timeSlot,
      scheduledEndDate: endTime,
    })
    
    stopDragging()
  }

  const getJobsInTimeSlot = (timeSlot: Date) => {
    return schedulingDraft.jobs.filter(job => {
      if (!job.scheduledStartDate) return false
      
      const jobStart = new Date(job.scheduledStartDate)
      const jobEnd = job.scheduledEndDate ? new Date(job.scheduledEndDate) : jobStart
      const slotEnd = new Date(timeSlot.getTime() + (preferences.timeScale === 'hours' ? 1 : preferences.timeScale === 'days' ? 24 : 168) * 60 * 60 * 1000)
      
      return (jobStart <= slotEnd && jobEnd >= timeSlot)
    })
  }

  const formatTimeSlot = (date: Date) => {
    if (preferences.timeScale === 'hours') {
      return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: 'numeric',
        hour12: true 
      })
    } else if (preferences.timeScale === 'days') {
      return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric',
        weekday: 'short'
      })
    } else {
      return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: preferences.timeScale === 'weeks' ? 'numeric' : undefined
      })
    }
  }

  return (
    <div className="space-y-4">
      {/* Timeline Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Scheduling Timeline</h2>
        <div className="text-sm text-gray-500">
          Scale: {preferences.timeScale} | {schedulingDraft.jobs.length} scheduled jobs
        </div>
      </div>

      {/* Timeline Grid */}
      <div className="overflow-x-auto">
        <div className="grid grid-cols-1 gap-2 min-w-full">
          {timelineData.map((timeSlot, index) => {
            const slotJobs = getJobsInTimeSlot(timeSlot)
            
            return (
              <Card
                key={index}
                className={`p-3 transition-colors ${
                  isDragging ? 'border-dashed border-blue-300 bg-blue-50' : ''
                }`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  if (draggedJobId) {
                    handleJobDrop(draggedJobId, timeSlot)
                  }
                }}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="font-medium text-sm">
                    {formatTimeSlot(timeSlot)}
                  </div>
                  {slotJobs.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {slotJobs.length} job{slotJobs.length > 1 ? 's' : ''}
                    </Badge>
                  )}
                </div>

                <div className="space-y-1">
                  {slotJobs.length === 0 ? (
                    <div className="text-xs text-gray-400 italic py-2">
                      Drop jobs here to schedule
                    </div>
                  ) : (
                    slotJobs.map((scheduledJob) => {
                      const originalJob = jobs.find(j => 
                        (j.id?.toString() || j.instance_id) === scheduledJob.jobId
                      )
                      
                      if (!originalJob) return null
                      
                      return (
                        <div
                          key={scheduledJob.jobId}
                          className={`p-2 rounded border text-xs ${
                            selectedJobs.includes(scheduledJob.jobId)
                              ? 'border-blue-500 bg-blue-100'
                              : 'border-gray-200 bg-white'
                          }`}
                        >
                          <div className="font-medium">
                            {originalJob.name || originalJob.serialNumber?.toString()}
                          </div>
                          <div className="text-gray-500 text-xs">
                            {originalJob.productType?.toString()} • {originalJob.priority}
                          </div>
                          {scheduledJob.scheduledStartDate && scheduledJob.scheduledEndDate && (
                            <div className="text-xs text-gray-400 mt-1">
                              {new Date(scheduledJob.scheduledStartDate).toLocaleTimeString('en-US', { 
                                hour: 'numeric', 
                                minute: '2-digit',
                                hour12: true 
                              })} - {new Date(scheduledJob.scheduledEndDate).toLocaleTimeString('en-US', { 
                                hour: 'numeric', 
                                minute: '2-digit',
                                hour12: true 
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      </div>

      {/* Unscheduled Jobs */}
      <Card>
        <div className="p-4">
          <h3 className="font-medium mb-3">Unscheduled Jobs</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {jobs
              .filter(job => {
                const jobId = job.id?.toString() || job.instance_id
                return !schedulingDraft.jobs.some(sj => sj.jobId === jobId)
              })
              .map((job) => {
                const jobId = job.id?.toString() || job.instance_id
                const isSelected = selectedJobs.includes(jobId)
                
                return (
                  <div
                    key={jobId}
                    draggable
                    onDragStart={() => startDragging(jobId)}
                    onDragEnd={() => stopDragging()}
                    className={`p-2 border rounded cursor-move transition-colors ${
                      isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                    } ${isDragging && draggedJobId === jobId ? 'opacity-50' : ''}`}
                    onClick={() => toggleJobSelection(jobId)}
                  >
                    <div className="font-medium text-sm">
                      {job.name || job.serialNumber?.toString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      {job.productType?.toString()}
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <Badge 
                        variant={job.priority === 'critical' ? 'destructive' : 'outline'}
                        className="text-xs"
                      >
                        {job.priority || 'medium'}
                      </Badge>
                      {job.dueDate && (
                        <div className="text-xs text-gray-400">
                          Due: {new Date(job.dueDate.toDate?.() || job.due_date).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
          
          {jobs.filter(job => {
            const jobId = job.id?.toString() || job.instance_id
            return !schedulingDraft.jobs.some(sj => sj.jobId === jobId)
          }).length === 0 && (
            <div className="text-center text-gray-500 py-4">
              All jobs have been scheduled
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}