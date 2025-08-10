import { Card, CardContent } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { FileText } from 'lucide-react'

interface JobTasksTabProps {
  tasks?: any[]
  tasksLoading: boolean
}

/**
 * Job Tasks Tab Component
 * Displays the complete list of tasks for the job
 */
export function JobTasksTab({ tasks, tasksLoading }: JobTasksTabProps) {
  if (tasksLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  if (!tasks || tasks.length === 0) {
    return (
      <div className="py-8 text-center">
        <FileText className="mx-auto mb-4 h-12 w-12 text-gray-300" />
        <h3 className="mb-2 text-lg font-medium">No Tasks</h3>
        <p className="text-sm text-gray-500">
          This job doesn&apos;t have any tasks defined yet.
        </p>
      </div>
    )
  }

  return (
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
  )
}