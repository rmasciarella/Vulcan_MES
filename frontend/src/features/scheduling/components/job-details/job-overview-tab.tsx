import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { Calendar, AlertCircle, ChevronRight } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import type { JobInstance } from '@/types/supabase'

interface JobOverviewTabProps {
  job: JobInstance
  tasks?: any[]
  tasksLoading: boolean
  dueDate: Date | null
  releaseDate: Date | null
  isOverdue: boolean
  onViewTasks: () => void
}

/**
 * Job Overview Tab Component
 * Displays job information, scheduling details, and tasks summary
 */
export function JobOverviewTab({
  job,
  tasks,
  tasksLoading,
  dueDate,
  releaseDate,
  isOverdue,
  onViewTasks,
}: JobOverviewTabProps) {
  return (
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
                    onClick={onViewTasks}
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
  )
}