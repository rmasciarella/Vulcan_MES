'use client'

import { useState, useCallback } from 'react'
import {
  useJob,
  useJobRealtime,
  useUpdateJobStatus,
  useDeleteJob,
} from '@/features/scheduling/hooks/use-jobs'
import { useTasks } from '@/features/scheduling/hooks/use-tasks'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { ManufacturingErrorBoundary, QueryErrorBoundary } from '@/shared/components/error-boundary'
import {
  ManufacturingLoadingState,
  DetailViewLoadingSkeleton,
  InlineLoadingState,
} from '@/shared/components/loading-states'
import {
  Calendar,
  Package,
  Clock,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  Edit,
  Trash2,
  RefreshCw,
  AlertCircle,
  ChevronRight,
  Info,
  FileText,
  Activity,
} from 'lucide-react'
import type { JobInstance } from '@/types/supabase'
import { cn } from '@/shared/lib/utils'

// Using direct JobInstance type from supabase types
type JobStatus = JobInstance['status']

interface JobDetailsPanelProps {
  jobId: string
  enableRealtime?: boolean
  onEdit?: (job: JobInstance) => void
  onClose?: () => void
  className?: string
}

const STATUS_CONFIG = {
  DRAFT: {
    label: 'Draft',
    icon: Edit,
    color: 'bg-gray-100 text-gray-800 border-gray-200',
    description: 'Job is being prepared and not yet ready for scheduling',
  },
  SCHEDULED: {
    label: 'Scheduled',
    icon: Calendar,
    color: 'bg-blue-100 text-blue-800 border-blue-200',
    description: 'Job has been scheduled and is waiting for execution',
  },
  IN_PROGRESS: {
    label: 'In Progress',
    icon: Play,
    color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    description: 'Job is currently being executed on the production floor',
  },
  ON_HOLD: {
    label: 'On Hold',
    icon: Pause,
    color: 'bg-orange-100 text-orange-800 border-orange-200',
    description: 'Job execution has been paused due to issues or resource constraints',
  },
  COMPLETED: {
    label: 'Completed',
    icon: CheckCircle2,
    color: 'bg-green-100 text-green-800 border-green-200',
    description: 'Job has been successfully completed and delivered',
  },
  CANCELLED: {
    label: 'Cancelled',
    icon: XCircle,
    color: 'bg-red-100 text-red-800 border-red-200',
    description: 'Job has been cancelled and will not be completed',
  },
}

/**
 * Job Details Panel - Comprehensive job information with real-time updates
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

  // Use real-time hook for live updates if enabled
  const realtimeJobQuery = useJobRealtime(jobId)
  const staticJobQuery = useJob(jobId)
  const jobQuery = enableRealtime ? realtimeJobQuery : staticJobQuery
  const { data: job, isLoading, isError, error } = jobQuery

  // Get related tasks for this job
  const { data: tasks, isLoading: tasksLoading } = useTasks({ jobId })

  const updateJobStatus = useUpdateJobStatus()
  const deleteJob = useDeleteJob()

  const handleStatusChange = useCallback(
    (newStatus: JobStatus) => {
      if (!job) return
      updateJobStatus.mutate({ id: job.instance_id, status: newStatus })
    },
    [job, updateJobStatus],
  )

  const handleDelete = useCallback(() => {
    if (!job) return
    if (
      window.confirm(
        `Are you sure you want to delete job ${job.name}? This action cannot be undone.`,
      )
    ) {
      deleteJob.mutate(job.instance_id, {
        onSuccess: () => onClose?.(),
      })
    }
  }, [job, deleteJob, onClose])

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="mb-2 h-6 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
            <Skeleton className="h-9 w-20" />
          </div>
        </CardHeader>
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
        <CardHeader>
          <CardTitle className="flex items-center text-red-600">
            <AlertCircle className="mr-2 h-5 w-5" />
            Error Loading Job
          </CardTitle>
        </CardHeader>
        <CardContent>
          <QueryErrorBoundary onRetry={() => jobQuery.refetch()}>
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {error?.message || `Job ${jobId} could not be found or loaded.`}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => jobQuery.refetch()}
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

  const statusConfig = STATUS_CONFIG[job.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.DRAFT
  const dueDate = job.due_date ? new Date(job.due_date) : null
  const releaseDate = job.earliest_start_date ? new Date(job.earliest_start_date) : null
  const isOverdue = dueDate && dueDate < new Date() && job.status !== 'COMPLETED'
  const canEdit = job.status !== 'COMPLETED' && job.status !== 'CANCELLED'

  const getAvailableTransitions = () => {
    const transitions: { status: JobStatus; label: string; icon: React.ComponentType }[] = []

    switch (job.status) {
      case 'DRAFT':
        transitions.push({ status: 'SCHEDULED', label: 'Schedule', icon: Calendar })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
      case 'SCHEDULED':
        transitions.push({ status: 'IN_PROGRESS', label: 'Start', icon: Play })
        transitions.push({ status: 'ON_HOLD', label: 'Hold', icon: Pause })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
      case 'IN_PROGRESS':
        transitions.push({ status: 'COMPLETED', label: 'Complete', icon: CheckCircle2 })
        transitions.push({ status: 'ON_HOLD', label: 'Hold', icon: Pause })
        break
      case 'ON_HOLD':
        transitions.push({ status: 'IN_PROGRESS', label: 'Resume', icon: Play })
        transitions.push({ status: 'CANCELLED', label: 'Cancel', icon: XCircle })
        break
    }

    return transitions
  }

  return (
    <ManufacturingErrorBoundary componentName="JobDetailsPanel" onRetry={() => jobQuery.refetch()}>
      <Card className={className}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="min-w-0 flex-1">
              <CardTitle className="flex items-center text-xl">
                <Package className="mr-2 h-6 w-6 flex-shrink-0" />
                <div className="truncate">
                  <span className="font-mono">{job.instance_id}</span>
                  {isOverdue && <AlertCircle className="ml-2 inline-block h-5 w-5 text-red-500" />}
                </div>
              </CardTitle>
              <CardDescription className="mt-2 flex items-center">
                <span className="truncate">{job.name}</span>
                {enableRealtime && (
                  <div className="ml-4 flex items-center text-green-600">
                    <div className="mr-1 h-2 w-2 animate-pulse rounded-full bg-green-500" />
                    <span className="text-xs">Live</span>
                  </div>
                )}
              </CardDescription>
            </div>

            <div className="flex items-center space-x-2">
              {canEdit && (
                <Button variant="outline" size="sm" onClick={() => onEdit?.(job)}>
                  <Edit className="mr-1 h-4 w-4" />
                  Edit
                </Button>
              )}
              {onClose && (
                <Button variant="ghost" size="sm" onClick={onClose}>
                  ×
                </Button>
              )}
            </div>
          </div>

          {/* Status and Quick Actions */}
          <div className="flex items-center justify-between border-t pt-4">
            <div className="flex items-center space-x-4">
              <Badge className={cn('px-3 py-1', statusConfig.color)}>
                <statusConfig.icon className="mr-2 h-4 w-4" />
                {statusConfig.label}
              </Badge>
              <span className="text-sm text-gray-600">{statusConfig.description}</span>
            </div>

            <div className="flex items-center space-x-2">
              {getAvailableTransitions().map((transition) => (
                <Button
                  key={transition.status}
                  variant="outline"
                  size="sm"
                  onClick={() => handleStatusChange(transition.status)}
                  disabled={updateJobStatus.isPending}
                >
                  {updateJobStatus.isPending ? (
                    <InlineLoadingState message={transition.label} size="xs" />
                  ) : (
                    <>
                      {(() => { const Icon = statusConfig.icon; return <Icon className="mr-1 h-4 w-4" /> })()}
                      {transition.label}
                    </>
                  )}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {/* Tabs */}
          <div className="mb-6 border-b border-gray-200">
            <nav className="flex space-x-8">
              {[
                { id: 'overview', label: 'Overview', icon: Info },
                { id: 'tasks', label: 'Tasks', icon: FileText, count: tasks?.length },
                { id: 'timeline', label: 'Timeline', icon: Clock },
                { id: 'logs', label: 'Logs', icon: Activity },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as 'overview' | 'tasks' | 'timeline' | 'logs')}
                  className={cn(
                    'flex items-center border-b-2 px-1 py-2 text-sm font-medium',
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
                  )}
                >
                  <tab.icon className="mr-2 h-4 w-4" />
                  {tab.label}
                  {tab.count !== undefined && (
                    <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-900">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Key Information */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Job Information</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <label className="text-sm font-medium text-gray-500">Product Type</label>
                      <p className="mt-1 text-sm">{job.description || 'Not specified'}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Template ID</label>
                      <p className="mt-1 font-mono text-sm">{job.template_id}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Version</label>
                      <p className="mt-1 text-sm">v{job.version || 1}</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Scheduling</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <label className="text-sm font-medium text-gray-500">Release Date</label>
                      <p
                        className={cn(
                          'mt-1 flex items-center text-sm',
                          releaseDate && releaseDate > new Date() && 'text-blue-600',
                        )}
                      >
                        <Calendar className="mr-2 h-4 w-4" />
                        {releaseDate ? releaseDate.toLocaleDateString() : 'Not set'}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Due Date</label>
                      <p
                        className={cn(
                          'mt-1 flex items-center text-sm',
                          isOverdue && 'font-medium text-red-600',
                        )}
                      >
                        <Calendar className="mr-2 h-4 w-4" />
                        {dueDate ? dueDate.toLocaleDateString() : 'Not set'}
                        {isOverdue && <AlertCircle className="ml-2 h-4 w-4" />}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Priority</label>
                      <p className="mt-1 text-sm">{isOverdue ? 'High (Overdue)' : 'Normal'}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Tasks Summary */}
              {tasks && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Tasks Overview</CardTitle>
                    <CardDescription>
                      {tasks.length} task{tasks.length !== 1 ? 's' : ''} in this job
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {tasksLoading ? (
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-4 w-1/2" />
                      </div>
                    ) : tasks.length === 0 ? (
                      <p className="text-sm text-gray-500">No tasks defined for this job yet.</p>
                    ) : (
                      <div className="space-y-2">
{tasks.slice(0, 3).map((task: any, _index: number) => (
                          <div
                            key={task.id}
                            className="flex items-center justify-between rounded border p-2"
                          >
                            <div>
                              <span className="text-sm font-medium">{task.name}</span>
                              <span className="ml-2 text-xs text-gray-500">
                                Seq: {task.sequence}
                              </span>
                            </div>
                            <Badge variant="outline" className="text-xs">
                              {task.status}
                            </Badge>
                          </div>
                        ))}
                        {tasks.length > 3 && (
                          <button
                            onClick={() => setActiveTab('tasks')}
                            className="flex items-center text-sm text-blue-600 hover:text-blue-800"
                          >
                            View all {tasks.length} tasks
                            <ChevronRight className="ml-1 h-4 w-4" />
                          </button>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Timestamps */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">History</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Created</span>
                    <span>
                      {job.created_at ? new Date(job.created_at).toLocaleString() : 'Unknown'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Last Updated</span>
                    <span>
                      {job.updated_at ? new Date(job.updated_at).toLocaleString() : 'Unknown'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {activeTab === 'tasks' && (
            <div>
              {tasksLoading ? (
                <div className="space-y-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : !tasks || tasks.length === 0 ? (
                <div className="py-8 text-center">
                  <FileText className="mx-auto mb-4 h-12 w-12 text-gray-300" />
                  <h3 className="mb-2 text-lg font-medium">No Tasks</h3>
                  <p className="text-sm text-gray-500">
                    This job doesn&apos;t have any tasks defined yet.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
{tasks.map((task: any, _index: number) => (
                    <Card key={task.id}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-medium">{task.name}</h4>
                            <p className="text-sm text-gray-500">
                              Sequence {task.sequence} •{' '}
                              {task.isSetupTask ? 'Setup Task' : 'Production Task'}
                            </p>
                          </div>
                          <Badge variant="outline">{task.status}</Badge>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'timeline' && (
            <div className="py-8 text-center">
              <Clock className="mx-auto mb-4 h-12 w-12 text-gray-300" />
              <h3 className="mb-2 text-lg font-medium">Timeline View</h3>
              <p className="text-sm text-gray-500">Timeline visualization coming soon...</p>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="py-8 text-center">
              <Activity className="mx-auto mb-4 h-12 w-12 text-gray-300" />
              <h3 className="mb-2 text-lg font-medium">Activity Logs</h3>
              <p className="text-sm text-gray-500">Job activity logs will be displayed here...</p>
            </div>
          )}

          {/* Danger Zone */}
          {canEdit && (
            <div className="mt-8 border-t border-red-200 pt-6">
              <h3 className="mb-4 text-lg font-medium text-red-800">Danger Zone</h3>
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-red-800">Delete Job</h4>
                    <p className="mt-1 text-sm text-red-600">
                      Permanently delete this job and all associated data.
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    onClick={handleDelete}
                    disabled={deleteJob.isPending}
                  >
                    {deleteJob.isPending ? (
                      <InlineLoadingState message="Deleting..." size="xs" />
                    ) : (
                      <>
                        <Trash2 className="mr-1 h-4 w-4" />
                        Delete Job
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </ManufacturingErrorBoundary>
  )
}
