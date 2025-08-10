import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { InlineLoadingState } from '@/shared/components/loading-states'
import { getStatusConfig } from '../../utils/job-status-config'
import { cn } from '@/shared/lib/utils'
import type { JobInstance } from '@/types/supabase'

type JobStatus = JobInstance['status']

interface JobStatusTransition {
  status: JobStatus
  label: string
  icon: React.ComponentType
}

interface JobStatusActionsProps {
  job: JobInstance
  availableTransitions: JobStatusTransition[]
  onStatusChange: (status: JobStatus) => void
  isUpdating: boolean
}

/**
 * Job Status Actions Component
 * Handles status badge display and transition buttons
 */
export function JobStatusActions({
  job,
  availableTransitions,
  onStatusChange,
  isUpdating,
}: JobStatusActionsProps) {
  const statusConfig = getStatusConfig(job.status)

  return (
    <div className="flex items-center justify-between border-t pt-4">
      <div className="flex items-center space-x-4">
        <Badge className={cn('px-3 py-1', statusConfig.color)}>
          <statusConfig.icon className="mr-2 h-4 w-4" />
          {statusConfig.label}
        </Badge>
        <span className="text-sm text-gray-600">{statusConfig.description}</span>
      </div>

      <div className="flex items-center space-x-2">
        {availableTransitions.map((transition) => (
          <Button
            key={transition.status}
            variant="outline"
            size="sm"
            onClick={() => onStatusChange(transition.status)}
            disabled={isUpdating}
          >
            {isUpdating ? (
              <InlineLoadingState message={transition.label} size="xs" />
            ) : (
              <>
                <transition.icon className="mr-1 h-4 w-4" />
                {transition.label}
              </>
            )}
          </Button>
        ))}
      </div>
    </div>
  )
}