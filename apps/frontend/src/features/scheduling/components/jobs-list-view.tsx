'use client'

import { useState, useMemo, useCallback } from 'react'
import {
  useJobs,
  useJobsInfinite,
  useUpdateJobStatus,
  useBulkUpdateJobStatus,
  type JobsListFilters,
} from '@/features/scheduling/hooks/use-jobs'
import dynamic from 'next/dynamic'
const VirtualizedTable = dynamic(() => import('@/shared/ui/virtualized-table').then(m => m.VirtualizedTable as any), {
  ssr: false,
  loading: () => null,
})
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Input } from '@/shared/ui/input'
import { ManufacturingErrorBoundary, QueryErrorBoundary } from '@/shared/components/error-boundary'
import {
  ManufacturingLoadingState,
  TableLoadingSkeleton,
  InlineLoadingState,
} from '@/shared/components/loading-states'
import {
  Calendar,
  Package,
  Search,
  RefreshCw,
  Edit,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from 'lucide-react'
import type { JobInstance } from '@/types/supabase'
import { cn } from '@/shared/lib/utils'

// Type compatibility: use Supabase types for now to enable compilation
// Using direct JobInstance type from supabase types
type JobStatus = JobInstance['status']

// Add minimal Job domain type compatibility for future migration
interface DomainJobCompat {
  id: string;
  serialNumber: string;
  productType: string;
  status: string;
  dueDate?: Date | null;
  tasks: any[];
  templateId: string;
}

interface JobsListViewProps {
  title?: string
  enableRealtime?: boolean
  enableVirtualization?: boolean
  initialFilters?: JobsListFilters
  height?: number
  pageSize?: number
  showFilters?: boolean
  showActions?: boolean
  showBulkActions?: boolean
  className?: string
  onJobClick?: (job: JobInstance) => void
  onJobEdit?: (job: JobInstance) => void
}

const STATUS_OPTIONS = [
  { value: 'DRAFT', label: 'Draft', icon: Edit },
  { value: 'SCHEDULED', label: 'Scheduled', icon: Calendar },
  { value: 'IN_PROGRESS', label: 'In Progress', icon: Play },
  { value: 'ON_HOLD', label: 'On Hold', icon: Pause },
  { value: 'COMPLETED', label: 'Completed', icon: CheckCircle2 },
  { value: 'CANCELLED', label: 'Cancelled', icon: XCircle },
] as const

const _SORT_OPTIONS = [
  { value: 'dueDate', label: 'Due Date' },
  { value: 'releaseDate', label: 'Release Date' },
  { value: 'status', label: 'Status' },
  { value: 'serialNumber', label: 'Serial Number' },
  { value: 'createdAt', label: 'Created Date' },
] as const

/**
 * Enhanced Jobs List View with virtualization support for 1000+ jobs
 * Features:
 * - Virtualized rendering for performance
 * - Real-time updates via Supabase subscriptions
 * - Advanced filtering and search
 * - Bulk operations for manufacturing efficiency
 * - Responsive design for manufacturing floor tablets
 * - Error boundaries and proper loading states
 */
export function JobsListView({
  title = 'Production Jobs',
  enableRealtime = true,
  enableVirtualization = true,
  initialFilters = {},
  height = 600,
  pageSize = 100,
  showFilters = true,
  showActions = true,
  showBulkActions = true,
  className,
  onJobClick,
  onJobEdit,
}: JobsListViewProps) {
  const [filters, _setFilters] = useState<JobsListFilters>(initialFilters)
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Apply search filter to the filters object
  const searchFilters = useMemo(
    () => ({
      ...filters,
      search: searchTerm.trim() || undefined,
    }),
    [filters, searchTerm],
  )

  // Use infinite query for virtualization or regular query for smaller datasets
  const infiniteQuery = useJobsInfinite(searchFilters, pageSize)
  const regularQuery = useJobs(searchFilters, { enableRealtime })
  const query = enableVirtualization ? infiniteQuery : regularQuery

  const updateJobStatus = useUpdateJobStatus()
  const bulkUpdateJobStatus = useBulkUpdateJobStatus()

  // Flatten infinite query data for virtualization
  const jobs = useMemo(() => {
    const data = query.data as any
    if (enableVirtualization && data && 'pages' in data) {
      return (data.pages as any[]).flatMap((page: any) => page.data) || []
    }
    return (data as any[]) || []
  }, [query.data, enableVirtualization])

  // Handle job selection for bulk operations
  const handleJobSelection = useCallback((jobId: string, checked: boolean) => {
    setSelectedJobs((prev) => {
      const newSet = new Set(prev)
      if (checked) {
        newSet.add(jobId)
      } else {
        newSet.delete(jobId)
      }
      return newSet
    })
  }, [])

  const handleSelectAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedJobs(new Set(jobs.map((job) => job.instance_id)))
      } else {
        setSelectedJobs(new Set())
      }
    },
    [jobs],
  )

  // Handle bulk status update
  const handleBulkStatusUpdate = useCallback(
    (newStatus: JobStatus) => {
      const updates = Array.from(selectedJobs).map((id) => ({ id, status: newStatus }))
      bulkUpdateJobStatus.mutate(updates, {
        onSuccess: () => {
          setSelectedJobs(new Set())
        },
      })
    },
    [selectedJobs, bulkUpdateJobStatus],
  )

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true)
    try {
      await query.refetch()
    } finally {
      setIsRefreshing(false)
    }
  }, [query])

  const getStatusConfig = useCallback((status: JobStatus) => {
    const config = STATUS_OPTIONS.find((option) => option.value === status)
    return config || STATUS_OPTIONS[0]
  }, [])

  const getStatusColor = useCallback((status: JobStatus) => {
    const colorMap: Record<string, string> = {
      DRAFT: 'bg-gray-100 text-gray-800 border-gray-200',
      SCHEDULED: 'bg-blue-100 text-blue-800 border-blue-200',
      IN_PROGRESS: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      ON_HOLD: 'bg-orange-100 text-orange-800 border-orange-200',
      COMPLETED: 'bg-green-100 text-green-800 border-green-200',
      CANCELLED: 'bg-red-100 text-red-800 border-red-200',
    }
    return colorMap[status] || colorMap['DRAFT']
  }, [])

  const renderJobRow = useCallback(
    (job: JobInstance, _index: number) => {
      const statusConfig = getStatusConfig(job.status)
      const isSelected = selectedJobs.has(job.instance_id)
      const dueDate = job.due_date ? new Date(job.due_date) : null
      const isOverdue = dueDate && dueDate < new Date() && job.status !== 'COMPLETED'

      return (
        <div
          key={job.instance_id}
          className={cn(
            'grid cursor-pointer grid-cols-12 gap-4 border-b p-4 transition-colors hover:bg-gray-50',
            isSelected && 'bg-blue-50',
            isOverdue && 'border-red-200 bg-red-50',
          )}
          onClick={() => onJobClick?.(job)}
        >
          {/* Selection - prevent event propagation */}
          {showBulkActions && (
            <div className="col-span-1 flex items-center" onClick={(e) => e.stopPropagation()}>
              <input
                type="checkbox"
                checked={isSelected}
                onChange={(e) => handleJobSelection(job.instance_id, e.target.checked)}
                className="rounded border-gray-300"
              />
            </div>
          )}

          {/* Job ID */}
          <div
            className={cn(
              'flex items-center font-mono text-sm',
              showBulkActions ? 'col-span-2' : 'col-span-3',
            )}
          >
            <div className="truncate">{job.instance_id}</div>
            {isOverdue && <AlertCircle className="ml-2 h-4 w-4 flex-shrink-0 text-red-500" />}
          </div>

          {/* Job Name */}
          <div className="col-span-2 flex min-w-0 items-center">
            <div className="min-w-0">
              <div className="truncate font-medium">{job.name}</div>
              <div className="truncate text-xs text-gray-500">{job.description}</div>
            </div>
          </div>

          {/* Template */}
          <div className="col-span-1 flex min-w-0 items-center text-sm text-gray-600">
            <div className="truncate">{job.template_id}</div>
          </div>

          {/* Due Date */}
          <div className="col-span-2 flex min-w-0 items-center text-sm">
            <Calendar className="mr-2 h-4 w-4 flex-shrink-0 text-gray-400" />
            <div className="min-w-0">
              <div className={cn('truncate font-medium', isOverdue && 'text-red-600')}>
                {dueDate ? dueDate.toLocaleDateString() : '-'}
              </div>
              <div className="truncate text-xs text-gray-500">
                {job.earliest_start_date
                  ? `Start: ${new Date(job.earliest_start_date).toLocaleDateString()}`
                  : 'No release date'}
              </div>
            </div>
          </div>

          {/* Status */}
          <div className="col-span-2 flex items-center">
            <Badge variant="secondary" className={cn('truncate', getStatusColor(job.status))}>
              {statusConfig.icon && <statusConfig.icon className="mr-1 h-3 w-3 flex-shrink-0" />}
              <span className="truncate">{statusConfig.label}</span>
            </Badge>
          </div>

          {/* Actions - prevent event propagation */}
          {showActions && (
            <div
              className="col-span-2 flex items-center justify-end space-x-1"
              onClick={(e) => e.stopPropagation()}
            >
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onJobEdit?.(job)}
                className="px-2 py-1 text-xs"
              >
                <Edit className="h-3 w-3" />
              </Button>
              {job.status !== 'COMPLETED' && job.status !== 'CANCELLED' && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const nextStatus =
                      job.status === 'DRAFT'
                        ? 'SCHEDULED'
                        : job.status === 'SCHEDULED'
                          ? 'IN_PROGRESS'
                          : 'COMPLETED'
                    updateJobStatus.mutate({ id: job.instance_id, status: nextStatus })
                  }}
                  disabled={updateJobStatus.isPending}
                  className="px-2 py-1 text-xs"
                >
                  {job.status === 'DRAFT' && <Calendar className="h-3 w-3" />}
                  {job.status === 'SCHEDULED' && <Play className="h-3 w-3" />}
                  {job.status === 'IN_PROGRESS' && <CheckCircle2 className="h-3 w-3" />}
                </Button>
              )}
            </div>
          )}
        </div>
      )
    },
    [
      selectedJobs,
      showBulkActions,
      showActions,
      getStatusConfig,
      getStatusColor,
      handleJobSelection,
      onJobClick,
      onJobEdit,
      updateJobStatus,
    ],
  )

  if (query.isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Package className="mr-2 h-5 w-5" />
            {title}
          </CardTitle>
          <CardDescription>Loading production jobs...</CardDescription>
        </CardHeader>
        <CardContent>
          <ManufacturingLoadingState
            type="jobs"
            message="Loading production jobs for manufacturing schedule..."
          />
          <div className="mt-6">
            <TableLoadingSkeleton rows={8} columns={6} />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (query.isError) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center text-red-600">
            <AlertCircle className="mr-2 h-5 w-5" />
            Production Data Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <QueryErrorBoundary onRetry={handleRefresh}>
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Failed to load production job data. This may affect production scheduling.
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="ml-4"
                >
                  {isRefreshing ? (
                    <InlineLoadingState message="Retrying..." />
                  ) : (
                    <>
                      <RefreshCw className="mr-1 h-4 w-4" />
                      Retry
                    </>
                  )}
                </Button>
              </AlertDescription>
            </Alert>
          </QueryErrorBoundary>
        </CardContent>
      </Card>
    )
  }

  const allSelected = jobs.length > 0 && selectedJobs.size === jobs.length
  const someSelected = selectedJobs.size > 0 && selectedJobs.size < jobs.length

  return (
    <ManufacturingErrorBoundary componentName="JobsListView" onRetry={() => query.refetch()}>
      <Card className={className}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <Package className="mr-2 h-5 w-5" />
                {title}
              </CardTitle>
              <CardDescription>
                {jobs.length} job{jobs.length !== 1 ? 's' : ''}
                {selectedJobs.size > 0 && ` • ${selectedJobs.size} selected`}
              </CardDescription>
            </div>

            <div className="flex items-center space-x-2">
              {enableRealtime && (
                <div className="flex items-center space-x-2 text-xs text-green-600">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                  Real-time
                </div>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing || query.isFetching}
              >
                <RefreshCw
                  className={cn('h-4 w-4', (isRefreshing || query.isFetching) && 'animate-spin')}
                />
              </Button>
            </div>
          </div>

          {/* Search */}
          {showFilters && (
            <div className="mt-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-gray-400" />
                <Input
                  placeholder="Search jobs by ID, name, or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
          )}

          {/* Bulk Actions */}
          {showBulkActions && selectedJobs.size > 0 && (
            <div className="mt-4 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 p-4">
              <div className="flex items-center space-x-4">
                <span className="text-sm font-medium">
                  {selectedJobs.size} job{selectedJobs.size !== 1 ? 's' : ''} selected
                </span>
                <Button variant="outline" size="sm" onClick={() => setSelectedJobs(new Set())}>
                  Clear Selection
                </Button>
              </div>

              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkStatusUpdate('SCHEDULED')}
                  disabled={bulkUpdateJobStatus.isPending}
                >
                  <Calendar className="mr-1 h-4 w-4" />
                  Schedule
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkStatusUpdate('IN_PROGRESS')}
                  disabled={bulkUpdateJobStatus.isPending}
                >
                  <Play className="mr-1 h-4 w-4" />
                  Start
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkStatusUpdate('ON_HOLD')}
                  disabled={bulkUpdateJobStatus.isPending}
                >
                  <Pause className="mr-1 h-4 w-4" />
                  Hold
                </Button>
              </div>
            </div>
          )}
        </CardHeader>

        <CardContent className="p-0">
          {/* Table Header */}
          <div className="sticky top-0 z-10 grid grid-cols-12 gap-4 border-b bg-gray-50 p-4 text-sm font-medium text-gray-700">
            {showBulkActions && (
              <div className="col-span-1 flex items-center">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someSelected
                  }}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="rounded border-gray-300"
                />
              </div>
            )}
            <div className={cn('flex items-center', showBulkActions ? 'col-span-2' : 'col-span-3')}>
              Job ID
            </div>
            <div className="col-span-2">Name</div>
            <div className="col-span-1">Template</div>
            <div className="col-span-2">Dates</div>
            <div className="col-span-2">Status</div>
            {showActions && <div className="col-span-2">Actions</div>}
          </div>

          {/* Jobs Table */}
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <Package className="mb-4 h-12 w-12 text-gray-300" />
              <h3 className="mb-2 text-lg font-medium">No jobs found</h3>
              <p className="max-w-md text-center text-sm">
                {searchTerm
                  ? `No jobs match your search "${searchTerm}". Try adjusting your search terms.`
                  : 'No production jobs are currently available. Jobs will appear here once they are created.'}
              </p>
            </div>
          ) : enableVirtualization ? (
            <div style={{ height: `${height}px` }}>
              <VirtualizedTable
                data={jobs}
                renderRow={renderJobRow}
                estimateRowHeight={80}
                overscan={10}
              />
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto">{jobs.map(renderJobRow)}</div>
          )}

          {/* Load More for Infinite Query */}
          {enableVirtualization && 'hasNextPage' in query && query.hasNextPage && (
            <div className="border-t p-4">
              <Button
                variant="outline"
                onClick={() => query.fetchNextPage()}
                disabled={query.isFetchingNextPage}
                className="w-full"
              >
                {query.isFetchingNextPage ? (
                  <InlineLoadingState message="Loading more jobs..." size="sm" />
                ) : (
                  `Load ${pageSize} more jobs`
                )}
              </Button>
            </div>
          )}

          {/* Footer with stats */}
          <div className="border-t bg-gray-50 p-4 text-sm text-gray-600">
            <div className="flex items-center justify-between">
              <div>
                Showing {jobs.length} jobs
                {enableVirtualization &&
                  'pages' in query.data &&
                  query.data.pages.length > 1 &&
                  ` (${query.data.pages.length} page${query.data.pages.length !== 1 ? 's' : ''} loaded)`}
              </div>
              <div className="flex gap-4">
                {STATUS_OPTIONS.map((status) => {
                  const count = jobs.filter((job) => job.status === status.value).length
                  return count > 0 ? (
                    <div key={status.value} className="flex items-center gap-1">
                      <div
                        className={`h-2 w-2 rounded-full ${getStatusColor(status.value).split(' ')[0]}`}
                      />
                      <span className="capitalize">
                        {status.label}: {count}
                      </span>
                    </div>
                  ) : null
                })}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </ManufacturingErrorBoundary>
  )
}
