import {
  Edit,
  Calendar,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import type { JobInstance } from '@/types/supabase'

type JobStatus = JobInstance['status']

export interface StatusConfig {
  label: string
  icon: React.ComponentType
  color: string
  description: string
}

export const STATUS_CONFIG: Record<string, StatusConfig> = {
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
 * Get status configuration for a job status
 */
export function getStatusConfig(status: JobStatus): StatusConfig {
  return STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.DRAFT
}