'use client'

import { useTasks, useTasksByJob } from '@/features/scheduling/hooks/use-tasks'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Task, type TaskStatusValue } from '@/core/domains/tasks'

interface TasksListProps {
  jobId?: string
  status?: TaskStatusValue
  title?: string
  showJobInfo?: boolean
  limit?: number
}

export function TasksList({
  jobId,
  status,
  title = 'Tasks',
  showJobInfo = true,
  limit,
}: TasksListProps) {
  // Always call hooks at top level - React rules of hooks
  const tasksByJobResult = useTasksByJob(jobId || '')
  const allTasksResult = useTasks({ status })

  // Use appropriate data based on filters
  const { data: tasks, isLoading, error } = jobId ? tasksByJobResult : allTasksResult

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>Loading tasks...</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center space-x-4">
              <Skeleton className="h-4 w-4" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-6 w-16" />
            </div>
          ))}
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertDescription>Failed to load tasks: {error.message}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  if (!tasks || tasks.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>No tasks found</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {jobId
              ? `No tasks found for job ${jobId}`
              : status
                ? `No tasks with status "${status}"`
                : 'No tasks available'}
          </p>
        </CardContent>
      </Card>
    )
  }

  const displayTasks = limit ? tasks.slice(0, limit) : tasks

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          {displayTasks.length} task{displayTasks.length !== 1 ? 's' : ''}
          {limit && tasks.length > limit && ` (showing first ${limit})`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {displayTasks.map((task) => (
            <TaskItem key={task.id.toString()} task={task} showJobInfo={showJobInfo} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

interface TaskItemProps {
  task: Task
  showJobInfo?: boolean
}

function TaskItem({ task, showJobInfo = true }: TaskItemProps) {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h4 className="text-sm font-medium">{task.name.toString()}</h4>
          <div className="flex items-center space-x-2 text-xs text-muted-foreground">
            <span>Sequence: {(task.sequence as any)?.value ?? task.sequence}</span>
            {showJobInfo && (
              <>
                <span>•</span>
                <span>Job: {task.jobId.toString()}</span>
              </>
            )}
          </div>
        </div>
        <TaskStatusBadge status={((task.status as any)?.getValue?.() ?? task.status) as TaskStatusValue} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center space-x-2 text-xs">
          <TaskAttendanceBadge isUnattended={(task.attendanceRequirement as any)?.isUnattended ?? false} />
          {task.isSetupTask && (
            <Badge variant="outline" className="text-xs">
              Setup Task
            </Badge>
          )}
        </div>

        <div className="space-y-1">
          <TaskResourceRequirements task={task} />
        </div>
      </div>

      <div className="flex items-center justify-between border-t pt-2">
        <div className="text-xs text-muted-foreground">
          Created: {task.createdAt.toLocaleDateString()}
        </div>
        <TaskActions task={task} />
      </div>
    </div>
  )
}

function TaskStatusBadge({ status }: { status: TaskStatusValue }) {
  const statusConfig: Record<string, { variant: any; label: string }> = {
    not_ready: { variant: 'secondary' as const, label: 'Not Ready' },
    ready: { variant: 'default' as const, label: 'Ready' },
    scheduled: { variant: 'outline' as const, label: 'Scheduled' },
    in_progress: { variant: 'default' as const, label: 'In Progress' },
    completed: { variant: 'secondary' as const, label: 'Completed' },
    on_hold: { variant: 'outline' as const, label: 'On Hold' },
    cancelled: { variant: 'destructive' as const, label: 'Cancelled' },
  }

  const config = statusConfig[status] || { variant: 'secondary' as const, label: status }

  return <Badge variant={config.variant}>{config.label}</Badge>
}

function TaskAttendanceBadge({ isUnattended }: { isUnattended: boolean }) {
  return (
    <Badge variant={isUnattended ? 'outline' : 'secondary'} className="text-xs">
      {isUnattended ? 'Unattended' : 'Attended'}
    </Badge>
  )
}

function TaskResourceRequirements({ task }: { task: Task }) {
  // Check if TaskModes are loaded
  if (!(task as any).areTaskModesLoaded?.()) {
    return (
      <div className="text-xs text-muted-foreground">
        <strong>Resources:</strong> <span className="italic">Loading task modes...</span>
      </div>
    )
  }

  const primaryMode = (task as any).getPrimaryMode?.()
  if (!primaryMode) {
    return (
      <div className="text-xs text-muted-foreground">
        <strong>Resources:</strong> <span className="italic">No execution modes defined</span>
      </div>
    )
  }

  return (
    <>
      <div className="text-xs text-muted-foreground">
        <strong>Skills:</strong>{' '}
        {primaryMode.skillRequirements.map((skill: any) => skill.toString()).join(', ') ||
          'None specified'}
      </div>
      <div className="text-xs text-muted-foreground">
        <strong>WorkCells:</strong>{' '}
        {primaryMode.workCellRequirements.map((wc: any) => wc.toString()).join(', ') || 'None specified'}
      </div>
      {(task as any).hasMultipleModes?.() && (
        <div className="text-xs text-muted-foreground">
          <strong>Modes:</strong> {task.taskModes?.length ?? 0} execution options available
        </div>
      )}
    </>
  )
}

function TaskActions({ task }: { task: Task }) {
  // Simple action buttons - would be expanded based on task status and user permissions
  const canMarkReady = ((task.status as any)?.getValue?.() ?? task.status) === 'not_ready'
  const canStart = ((task.status as any)?.getValue?.() ?? task.status) === 'scheduled'
  const canComplete = ((task.status as any)?.getValue?.() ?? task.status) === 'in_progress'

  return (
    <div className="flex items-center space-x-1">
      {canMarkReady && (
        <Button size="sm" variant="outline" className="text-xs">
          Mark Ready
        </Button>
      )}
      {canStart && (
        <Button size="sm" variant="outline" className="text-xs">
          Start
        </Button>
      )}
      {canComplete && (
        <Button size="sm" variant="default" className="text-xs">
          Complete
        </Button>
      )}
    </div>
  )
}
