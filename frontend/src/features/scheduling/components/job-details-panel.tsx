'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/shared/ui/card'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Button } from '@/shared/ui/button'
import { ManufacturingErrorBoundary, QueryErrorBoundary } from '@/shared/components/error-boundary'
import {
  ManufacturingLoadingState,
  DetailViewLoadingSkeleton,
} from '@/shared/components/loading-states'
import { AlertCircle, RefreshCw } from 'lucide-react'
import type { JobInstance } from '@/types/supabase'
import { 
  useJobDetailsData, 
  useJobStatusTransitions, 
  useJobActions 
} from '@/features/scheduling/hooks/use-job-details'
import { JobDetailsHeader } from './job-details/job-details-header'
import { JobStatusActions } from './job-details/job-status-actions'
import { JobNavigationTabs } from './job-details/job-navigation-tabs'
import { JobOverviewTab } from './job-details/job-overview-tab'
import { JobTasksTab } from './job-details/job-tasks-tab'
import { JobTimelineTab } from './job-details/job-timeline-tab'
import { JobLogsTab } from './job-details/job-logs-tab'
import { JobDangerZone } from './job-details/job-danger-zone'

interface JobDetailsPanelProps {
  jobId: string
  enableRealtime?: boolean
  onEdit?: (job: JobInstance) => void
  onClose?: () => void
  className?: string
}

/**
 * Job Details Panel - Comprehensive job information with real-time updates
 * Refactored into focused components following Single Responsibility Principle
 * Features:
 * - Real-time job status monitoring
 * - Task list integration  
 * - Status transition controls
 * - Manufacturing context awareness
 * - Edit and delete capabilities
 * - Responsive design for tablets
 */
export function JobDetailsPanel({
  jobId,
  enableRealtime = true,
  onEdit,
  onClose,
  className,
}: JobDetailsPanelProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'tasks' | 'timeline' | 'logs'>('overview')

  // Use extracted hooks for data, business logic, and actions
  const { job, tasks, isLoading, isError, error, tasksLoading, refetch } = useJobDetailsData({ 
    jobId, 
    enableRealtime 
  })
  
  const { getAvailableTransitions, canEdit, dueDate, releaseDate, isOverdue } = useJobStatusTransitions(job)
  const { handleStatusChange, handleDelete, updateJobStatus, deleteJob } = useJobActions(job, onClose)

  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent>
          <ManufacturingLoadingState type="jobs" message="Loading job details..." />
          <DetailViewLoadingSkeleton />
        </CardContent>
      </Card>
    )
  }

  if (isError || !job) {
    return (
      <Card className={className}>
        <CardContent>
          <QueryErrorBoundary onRetry={() => refetch()}>
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {error?.message || `Job ${jobId} could not be found or loaded.`}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetch()}
                  className="ml-4"
                >
                  <RefreshCw className="mr-1 h-4 w-4" />
                  Retry
                </Button>
              </AlertDescription>
            </Alert>
          </QueryErrorBoundary>
        </CardContent>
      </Card>
    )
  }

  const availableTransitions = getAvailableTransitions()

  return (
    <ManufacturingErrorBoundary componentName="JobDetailsPanel" onRetry={() => refetch()}>
      <Card className={className}>
        <JobDetailsHeader
          job={job}
          enableRealtime={enableRealtime}
          canEdit={canEdit}
          isOverdue={isOverdue}
          onEdit={onEdit}
          onClose={onClose}
        />
        
        <JobStatusActions
          job={job}
          availableTransitions={availableTransitions}
          onStatusChange={handleStatusChange}
          isUpdating={updateJobStatus.isPending}
        />

        <CardContent>
          <JobNavigationTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            {...(tasks?.length !== undefined && { tasksCount: tasks.length })}
          />

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <JobOverviewTab
              job={job}
              tasks={tasks}
              tasksLoading={tasksLoading}
              dueDate={dueDate}
              releaseDate={releaseDate}
              isOverdue={isOverdue}
              onViewTasks={() => setActiveTab('tasks')}
            />
          )}

          {activeTab === 'tasks' && (
            <JobTasksTab 
              {...(tasks !== undefined && { tasks })} 
              tasksLoading={tasksLoading} 
            />
          )}

          {activeTab === 'timeline' && (
            <JobTimelineTab />
          )}

          {activeTab === 'logs' && (
            <JobLogsTab />
          )}

          {/* Danger Zone */}
          {canEdit && (
            <JobDangerZone
              onDelete={handleDelete}
              isDeleting={deleteJob.isPending}
            />
          )}
        </CardContent>
      </Card>
    </ManufacturingErrorBoundary>
  )
}
