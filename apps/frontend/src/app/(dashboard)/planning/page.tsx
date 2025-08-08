import { Suspense } from 'react'
import { JobsList } from './_components/jobs-list'
import { TasksList } from './_components/tasks-list'
import { ManufacturingLoadingState } from '@/shared/components/loading-states'

export default function PlanningPage() {
  return (
    <div className="space-y-6 p-6">
      {/* Main Jobs Section */}
      <div className="space-y-6">
        <Suspense
          fallback={<ManufacturingLoadingState type="jobs" message="Loading production jobs..." />}
        >
          <JobsList />
        </Suspense>
      </div>

      {/* Task Overview Sections */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Suspense fallback={<ManufacturingLoadingState type="tasks" />}>
          <TasksList title="Ready for Scheduling" status={'ready' as any} showJobInfo={false} limit={5} />
        </Suspense>

        <Suspense fallback={<ManufacturingLoadingState type="tasks" />}>
          <TasksList title="In Progress" status={'in_progress' as any} showJobInfo={false} limit={5} />
        </Suspense>

        <Suspense fallback={<ManufacturingLoadingState type="tasks" />}>
          <TasksList title="Setup Required" showJobInfo={false} limit={5} />
        </Suspense>
      </div>
    </div>
  )
}