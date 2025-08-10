import { Button } from '@/shared/ui/button'
import { InlineLoadingState } from '@/shared/components/loading-states'
import { Trash2 } from 'lucide-react'

interface JobDangerZoneProps {
  onDelete: () => void
  isDeleting: boolean
}

/**
 * Job Danger Zone Component
 * Handles destructive actions like job deletion
 */
export function JobDangerZone({ onDelete, isDeleting }: JobDangerZoneProps) {
  return (
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
            onClick={onDelete}
            disabled={isDeleting}
          >
            {isDeleting ? (
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
  )
}