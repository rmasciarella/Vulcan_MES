import React from 'react'
import { Card } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Select } from '@/shared/ui/select'
import { Input } from '@/shared/ui/input'
import { Checkbox } from '@/shared/ui/checkbox'
import { 
  useJobScheduling, 
  useJobsForScheduling, 
  useBatchScheduleJobs,
  useAutoScheduleJobs,
  useJobSchedulingPreferences,
  useSchedulingConflicts
} from '../hooks/use-job-scheduling'
import type { JobPriority } from '../../scheduling/types/jobs'

export function JobSchedulingDashboard() {
  const {
    currentView,
    selectedJobs,
    filters,
    schedulingDraft,
    setView,
    setFilters,
    toggleJobSelection,
    selectAllJobs,
    clearSelection,
  } = useJobScheduling()

  const {
    preferences,
    toggleAutoSchedule,
    toggleShowDependencies,
    toggleGroupByPriority,
    setTimeScale,
  } = useJobSchedulingPreferences()

  const { data: jobs, isLoading } = useJobsForScheduling()
  const batchScheduleMutation = useBatchScheduleJobs()
  const autoScheduleMutation = useAutoScheduleJobs()
  const { conflicts, hasConflicts } = useSchedulingConflicts()

  const handlePriorityFilter = (priority: string) => {
    if (priority === 'all') {
      const { priority: _, ...filtersWithoutPriority } = filters
      setFilters(filtersWithoutPriority)
    } else {
      setFilters({ priority: priority as JobPriority })
    }
  }

  const handleSearchFilter = (search: string) => {
    setFilters({ search })
  }

  const handleDateRangeFilter = (startDate: string, endDate: string) => {
    if (startDate && endDate) {
      setFilters({
        dateRange: {
          start: new Date(startDate),
          end: new Date(endDate),
        },
      })
    }
  }

  const handleBatchSchedule = () => {
    if (schedulingDraft.jobs.length > 0) {
      batchScheduleMutation.mutate({ jobs: schedulingDraft.jobs })
    }
  }

  const handleAutoSchedule = () => {
    if (selectedJobs.length > 0) {
      autoScheduleMutation.mutate(selectedJobs)
    }
  }

  const handleSelectAll = () => {
    if (jobs) {
      const jobIds = jobs.map(job => job.id?.toString() || job.instance_id)
      selectAllJobs(jobIds)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Job Scheduling</h1>
        <div className="flex items-center gap-2">
          <Button
            onClick={handleAutoSchedule}
            disabled={selectedJobs.length === 0 || autoScheduleMutation.isPending}
            variant="outline"
          >
            {autoScheduleMutation.isPending ? 'Auto-Scheduling...' : 'Auto Schedule'}
          </Button>
          <Button
            onClick={handleBatchSchedule}
            disabled={schedulingDraft.jobs.length === 0 || batchScheduleMutation.isPending}
          >
            {batchScheduleMutation.isPending ? 'Scheduling...' : `Schedule ${schedulingDraft.jobs.length} Jobs`}
          </Button>
        </div>
      </div>

      {/* Conflicts Alert */}
      {hasConflicts && (
        <Card className="border-red-200 bg-red-50">
          <div className="p-4">
            <h3 className="font-medium text-red-800 mb-2">Scheduling Conflicts Detected</h3>
            <div className="space-y-1">
              {conflicts.map((conflict, index) => (
                <div key={index} className="text-sm text-red-600">
                  Job {conflict.jobId}: {conflict.description}
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Filters and Controls */}
      <Card>
        <div className="p-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            {/* View Selector */}
            <div>
              <label className="block text-sm font-medium mb-1">View</label>
              <Select
                value={currentView}
                onValueChange={(value) => setView(value as any)}
              >
                <option value="timeline">Timeline</option>
                <option value="kanban">Kanban</option>
                <option value="list">List</option>
              </Select>
            </div>

            {/* Priority Filter */}
            <div>
              <label className="block text-sm font-medium mb-1">Priority</label>
              <Select
                value={filters.priority || 'all'}
                onValueChange={handlePriorityFilter}
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </Select>
            </div>

            {/* Search */}
            <div>
              <label className="block text-sm font-medium mb-1">Search</label>
              <Input
                type="text"
                placeholder="Search jobs..."
                value={filters.search || ''}
                onChange={(e) => handleSearchFilter(e.target.value)}
              />
            </div>

            {/* Time Scale */}
            <div>
              <label className="block text-sm font-medium mb-1">Time Scale</label>
              <Select
                value={preferences.timeScale}
                onValueChange={(value) => setTimeScale(value as any)}
              >
                <option value="hours">Hours</option>
                <option value="days">Days</option>
                <option value="weeks">Weeks</option>
              </Select>
            </div>
          </div>

          {/* Preferences */}
          <div className="flex flex-wrap gap-4 pt-2 border-t">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="auto-schedule"
                checked={preferences.autoSchedule}
                onCheckedChange={toggleAutoSchedule}
              />
              <label htmlFor="auto-schedule" className="text-sm">Auto Schedule</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="show-dependencies"
                checked={preferences.showDependencies}
                onCheckedChange={toggleShowDependencies}
              />
              <label htmlFor="show-dependencies" className="text-sm">Show Dependencies</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="group-by-priority"
                checked={preferences.groupByPriority}
                onCheckedChange={toggleGroupByPriority}
              />
              <label htmlFor="group-by-priority" className="text-sm">Group by Priority</label>
            </div>
          </div>
        </div>
      </Card>

      {/* Selection Controls */}
      {jobs && jobs.length > 0 && (
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">
              {selectedJobs.length} of {jobs.length} jobs selected
            </span>
            <Button variant="outline" size="sm" onClick={handleSelectAll}>
              Select All
            </Button>
            <Button variant="outline" size="sm" onClick={clearSelection}>
              Clear Selection
            </Button>
          </div>
          {schedulingDraft.isDirty && (
            <Badge variant="outline">
              {schedulingDraft.jobs.length} jobs in draft schedule
            </Badge>
          )}
        </div>
      )}

      {/* Jobs View */}
      <Card>
        <div className="p-4">
          {currentView === 'list' && (
            <JobSchedulingListView
              jobs={jobs || []}
              selectedJobs={selectedJobs}
              onToggleSelection={toggleJobSelection}
              groupByPriority={preferences.groupByPriority}
            />
          )}
          {currentView === 'timeline' && (
            <div className="text-center text-gray-500 py-8">
              Timeline view would be implemented here with job scheduling timeline
            </div>
          )}
          {currentView === 'kanban' && (
            <div className="text-center text-gray-500 py-8">
              Kanban view would be implemented here with job scheduling board
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

// Simple list view component for jobs
function JobSchedulingListView({ 
  jobs, 
  selectedJobs, 
  onToggleSelection,
  groupByPriority 
}: {
  jobs: any[]
  selectedJobs: string[]
  onToggleSelection: (jobId: string) => void
  groupByPriority: boolean
}) {
  if (!jobs || jobs.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        No jobs found. Adjust your filters or create new jobs.
      </div>
    )
  }

  const organizedJobs = groupByPriority 
    ? jobs.reduce((acc, job) => {
        const priority = job.priority || 'medium'
        if (!acc[priority]) acc[priority] = []
        acc[priority].push(job)
        return acc
      }, {} as Record<string, any[]>)
    : { 'All Jobs': jobs }

  return (
    <div className="space-y-4">
      {Object.entries(organizedJobs).map(([groupName, groupJobs]) => (
        <div key={groupName}>
          {groupByPriority && (
            <h3 className="font-medium text-sm text-gray-700 mb-2 uppercase tracking-wide">
              {groupName} Priority ({groupJobs.length})
            </h3>
          )}
          <div className="space-y-2">
            {groupJobs.map((job) => {
              const jobId = job.id?.toString() || job.instance_id
              const isSelected = selectedJobs.includes(jobId)
              
              return (
                <div
                  key={jobId}
                  className={`flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-colors ${
                    isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => onToggleSelection(jobId)}
                >
                  <div className="flex items-center space-x-3">
                    <Checkbox checked={isSelected} readOnly />
                    <div>
                      <div className="font-medium">{job.name || job.serialNumber?.toString()}</div>
                      <div className="text-sm text-gray-500">
                        {job.productType?.toString()} • Status: {job.status?.toString() || job.status}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge variant={job.priority === 'critical' ? 'destructive' : 'outline'}>
                      {job.priority || 'medium'}
                    </Badge>
                    {job.dueDate && (
                      <div className="text-sm text-gray-500">
                        Due: {new Date(job.dueDate.toDate?.() || job.due_date).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}