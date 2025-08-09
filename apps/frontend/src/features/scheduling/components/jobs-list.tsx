'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import {
  AlertCircle,
  Calendar,
  Package,
  Plus,
  Search,
  MoreVertical,
  Eye,
  Play,
  Pause,
} from 'lucide-react'
import { VirtualizedJobTable } from '@/shared/ui/virtualized-job-table'
import { Job, JobStatusValue } from '../types/jobs'
import { useJobs, useUpdateJobStatus } from '../hooks/use-jobs'
import { useUIStore } from '@/core/stores/ui-store'

export function JobsList(): React.JSX.Element {
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')
  const [statusFilter, setStatusFilter] = useState<keyof typeof JobStatusValue | undefined>()
  const [searchTerm, setSearchTerm] = useState('')
  const addNotification = useUIStore((state) => state.addNotification)

  const {
    data: jobs,
    isLoading,
    error,
    refetch,
  } = useJobs(
    {
      status: statusFilter,
      search: searchTerm,
    },
    {
      enableRealtime: true,
    },
  )

  const updateJobStatus = useUpdateJobStatus()

  const handleJobAction = async (jobId: string, action: string): Promise<void> => {
    try {
      switch (action) {
        case 'schedule':
          await updateJobStatus.mutateAsync({
            id: jobId,
            status: JobStatusValue.SCHEDULED,
          })
          break
        case 'start':
          await updateJobStatus.mutateAsync({
            id: jobId,
            status: JobStatusValue.IN_PROGRESS,
          })
          break
        case 'pause':
          await updateJobStatus.mutateAsync({
            id: jobId,
            status: JobStatusValue.ON_HOLD,
          })
          break
        case 'view':
          // TODO: Navigate to job details page
          addNotification({
            type: 'info',
            title: 'Job Details',
            message: `Viewing details for job ${jobId}`,
          })
          break
      }
    } catch (error) {
      addNotification({
        type: 'error',
        title: 'Action Failed',
        message: error instanceof Error ? error.message : 'Unknown error occurred',
      })
    }
  }

  const filteredJobs: Job[] = (jobs as Job[] | undefined)?.filter((job: Job) => {
      const matchesSearch =
        searchTerm === '' ||
        job.serialNumber.toString().toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.productType.toString().toLowerCase().includes(searchTerm.toLowerCase())
      return matchesSearch
    }) || []

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Production Jobs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-600">
            <AlertCircle className="h-5 w-5" />
            Production Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              Unable to load production jobs. This may affect scheduling operations.
              <div className="mt-3 flex gap-2">
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
                <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
                  Reload Page
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Production Jobs
            </CardTitle>
            <p className="mt-1 text-sm text-gray-600">
              {filteredJobs.length} job{filteredJobs.length !== 1 ? 's' : ''}
              {statusFilter && ` with status "${statusFilter}"`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Plus className="mr-2 h-4 w-4" />
              New Job
            </Button>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="mt-4 flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-gray-400" />
            <input
              type="text"
              placeholder="Search jobs..."
              className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 text-sm"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            value={statusFilter || ''}
            onChange={(e) => setStatusFilter((e.target.value as keyof typeof JobStatusValue) || undefined)}
          >
            <option value="">All Status</option>
            <option value={JobStatusValue.DRAFT}>Draft</option>
            <option value={JobStatusValue.SCHEDULED}>Scheduled</option>
            <option value={JobStatusValue.IN_PROGRESS}>In Progress</option>
            <option value={JobStatusValue.ON_HOLD}>On Hold</option>
            <option value={JobStatusValue.COMPLETED}>Completed</option>
          </select>
          <div className="flex items-center rounded-lg border border-gray-300">
            <Button
              variant={viewMode === 'cards' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('cards')}
              className="rounded-r-none"
            >
              Cards
            </Button>
            <Button
              variant={viewMode === 'table' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('table')}
              className="rounded-l-none"
            >
              Table
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {filteredJobs.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <Package className="mx-auto mb-4 h-12 w-12 text-gray-300" />
            <h3 className="mb-2 font-medium">No jobs found</h3>
            <p className="text-sm">
              {jobs?.length === 0
                ? 'No production jobs have been created yet.'
                : 'No jobs match your current filters.'}
            </p>
            <Button variant="outline" className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Create First Job
            </Button>
          </div>
        ) : viewMode === 'table' ? (
          <div className="-mx-6">
            <VirtualizedJobTable
              jobs={filteredJobs.map((job) => ({
                instance_id: job.id.toString(),
                name: job.serialNumber.toString(),
                description: job.productType.toString(),
                status: job.status.toString(),
                due_date: job.dueDate?.toDate().toISOString() || null,
              }))}
              height={400}
              onJobClick={(job: any) => handleJobAction(job.instance_id, 'view')}
              onStatusChange={(jobId: string, status: string) => handleJobAction(jobId, status.toLowerCase())}
            />
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredJobs.map((job: Job) => (
              <JobCard key={job.id.toString()} job={job} onAction={handleJobAction} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface JobCardProps {
  job: Job;
  onAction: (jobId: string, action: string) => void;
}

function JobCard({ job, onAction }: JobCardProps): React.JSX.Element {
  const getStatusColor = (status: keyof typeof JobStatusValue): string => {
    switch (status) {
      case JobStatusValue.DRAFT:
        return 'bg-gray-100 text-gray-800'
      case JobStatusValue.SCHEDULED:
        return 'bg-blue-100 text-blue-800'
      case JobStatusValue.IN_PROGRESS:
        return 'bg-yellow-100 text-yellow-800'
      case JobStatusValue.ON_HOLD:
        return 'bg-orange-100 text-orange-800'
      case JobStatusValue.COMPLETED:
        return 'bg-green-100 text-green-800'
      case JobStatusValue.CANCELLED:
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const statusValue = job.status.toString() as keyof typeof JobStatusValue
  const dueDate = job.dueDate
  const formattedDueDate = dueDate ? new Date(dueDate.toDate()).toLocaleDateString() : 'No due date'

  const canSchedule = statusValue === JobStatusValue.DRAFT
  const canStart = statusValue === JobStatusValue.SCHEDULED
  const canPause = statusValue === JobStatusValue.IN_PROGRESS

  return (
    <Card className="group transition-shadow hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{job.serialNumber.toString()}</CardTitle>
            <p className="mt-1 text-sm text-gray-600">{job.productType.toString()}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className={getStatusColor(statusValue)}>
              {statusValue.replace('_', ' ')}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-1 opacity-0 transition-opacity group-hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation()
                // TODO: Add dropdown menu for more actions
              }}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-3">
          <div className="space-y-2">
            <div className="flex items-center text-sm text-gray-600">
              <Calendar className="mr-2 h-4 w-4" />
              <span>Due: {formattedDueDate}</span>
            </div>

            {/* TODO: Add tasks count when task integration is complete */}
            <div className="flex items-center text-sm text-gray-600">
              <Package className="mr-2 h-4 w-4" />
              <span>Priority: {job.priority}</span>
            </div>

            <div className="text-sm text-gray-600">Template: {job.templateId}</div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 border-t pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAction(job.id.toString(), 'view')}
              className="flex-1"
            >
              <Eye className="mr-1 h-4 w-4" />
              View
            </Button>

            {canSchedule && (
              <Button
                variant="default"
                size="sm"
                onClick={() => onAction(job.id.toString(), 'schedule')}
                className="flex-1"
              >
                <Calendar className="mr-1 h-4 w-4" />
                Schedule
              </Button>
            )}

            {canStart && (
              <Button
                variant="default"
                size="sm"
                onClick={() => onAction(job.id.toString(), 'start')}
                className="flex-1"
              >
                <Play className="mr-1 h-4 w-4" />
                Start
              </Button>
            )}

            {canPause && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onAction(job.id.toString(), 'pause')}
                className="flex-1"
              >
                <Pause className="mr-1 h-4 w-4" />
                Pause
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}