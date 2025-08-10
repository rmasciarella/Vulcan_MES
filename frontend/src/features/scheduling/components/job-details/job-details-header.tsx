import { CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Package, AlertCircle, Edit } from 'lucide-react'
import type { JobInstance } from '@/types/supabase'

interface JobDetailsHeaderProps {
  job: JobInstance
  enableRealtime?: boolean
  canEdit: boolean
  isOverdue: boolean
  onEdit?: (job: JobInstance) => void
  onClose?: () => void
}

/**
 * Job Details Header Component
 * Handles the job title, description, realtime indicator, and action buttons
 */
export function JobDetailsHeader({
  job,
  enableRealtime = true,
  canEdit,
  isOverdue,
  onEdit,
  onClose,
}: JobDetailsHeaderProps) {
  return (
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
    </CardHeader>
  )
}