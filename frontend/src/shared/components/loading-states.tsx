import React from 'react'
import { Loader2, Clock, Database, BarChart3, Calendar, Settings } from 'lucide-react'
import { Skeleton } from '@/shared/ui/skeleton'

/**
 * Generic loading spinner
 */
export function LoadingSpinner({
  size = 'default',
  message,
}: {
  size?: 'sm' | 'default' | 'lg'
  message?: string
}) {
  const iconSize = {
    sm: 'h-4 w-4',
    default: 'h-6 w-6',
    lg: 'h-8 w-8',
  }

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <Loader2 className={`animate-spin text-blue-600 ${iconSize[size]}`} />
      {message && <p className="mt-2 text-sm text-gray-600">{message}</p>}
    </div>
  )
}

/**
 * Manufacturing-specific loading states
 */
export function ManufacturingLoadingState({
  type = 'default',
  message,
}: {
  type?: 'jobs' | 'tasks' | 'resources' | 'schedule' | 'optimization' | 'default'
  message?: string
}) {
  const icons = {
    jobs: Database,
    tasks: Clock,
    resources: Settings,
    schedule: Calendar,
    optimization: BarChart3,
    default: Loader2,
  }

  const Icon = icons[type]

  const defaultMessages = {
    jobs: 'Loading production jobs...',
    tasks: 'Loading task assignments...',
    resources: 'Loading resource availability...',
    schedule: 'Generating production schedule...',
    optimization: 'Optimizing schedule parameters...',
    default: 'Loading manufacturing data...',
  }

  const displayMessage = message || defaultMessages[type]

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <Icon className="mb-3 h-8 w-8 animate-spin text-blue-600" />
      <h3 className="mb-1 font-medium text-gray-900">Manufacturing System</h3>
      <p className="text-sm text-gray-600">{displayMessage}</p>
    </div>
  )
}

/**
 * Table loading skeleton
 */
export function TableLoadingSkeleton({
  rows = 5,
  columns = 4,
}: {
  rows?: number
  columns?: number
}) {
  return (
    <div className="space-y-3">
      {/* Header skeleton */}
      <div className="flex space-x-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>

      {/* Row skeletons */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex space-x-4">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={colIndex} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * Card grid loading skeleton
 */
export function CardGridLoadingSkeleton({
  count = 6,
  columns = 3,
}: {
  count?: number
  columns?: number
}) {
  return (
    <div className={`grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-${columns}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-gray-200 p-6">
          <Skeleton className="mb-3 h-4 w-3/4" />
          <Skeleton className="mb-4 h-8 w-1/2" />
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Chart loading skeleton
 */
export function ChartLoadingSkeleton({
  height = 'h-64',
  title,
}: {
  height?: string
  title?: string
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-6">
      {title && <Skeleton className="mb-4 h-6 w-48" />}
      <div className={`${height} flex items-end justify-between space-x-2`}>
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton
            key={i}
            className={`w-full`}
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>
    </div>
  )
}

/**
 * Timeline/Gantt loading skeleton
 */
export function TimelineLoadingSkeleton() {
  return (
    <div className="space-y-4">
      {/* Timeline header */}
      <div className="flex space-x-4 border-b pb-2">
        <Skeleton className="h-4 w-32" />
        <div className="flex flex-1 justify-between">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-16" />
          ))}
        </div>
      </div>

      {/* Timeline rows */}
      {Array.from({ length: 6 }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex items-center space-x-4">
          <Skeleton className="h-6 w-32" />
          <div className="flex flex-1 space-x-2">
            {Array.from({ length: Math.floor(Math.random() * 4) + 1 }).map((_, barIndex) => (
              <Skeleton
                key={barIndex}
                className="h-8"
                style={{
                  width: `${Math.random() * 200 + 50}px`,
                  marginLeft: `${Math.random() * 100}px`,
                }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Form loading skeleton
 */
export function FormLoadingSkeleton({ fields = 6 }: { fields?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <div className="flex space-x-2 pt-4">
        <Skeleton className="h-10 w-20" />
        <Skeleton className="h-10 w-16" />
      </div>
    </div>
  )
}

/**
 * Detailed item loading skeleton
 */
export function DetailViewLoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b pb-4">
        <Skeleton className="mb-2 h-8 w-64" />
        <Skeleton className="h-4 w-32" />
      </div>

      {/* Sections */}
      {Array.from({ length: 3 }).map((_, sectionIndex) => (
        <div key={sectionIndex} className="space-y-3">
          <Skeleton className="h-6 w-40" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, fieldIndex) => (
              <div key={fieldIndex} className="space-y-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Full page loading state
 */
export function PageLoadingState({
  title = 'Loading Manufacturing System',
  message = 'Please wait while we load your data...',
}: {
  title?: string
  message?: string
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-blue-600" />
        <h2 className="mb-2 text-lg font-semibold text-gray-900">{title}</h2>
        <p className="text-sm text-gray-600">{message}</p>
      </div>
    </div>
  )
}

/**
 * Inline loading state for buttons and small components
 */
export function InlineLoadingState({
  message,
  size = 'sm',
}: {
  message?: string
  size?: 'xs' | 'sm' | 'md'
}) {
  const iconSize = {
    xs: 'h-3 w-3',
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
  }

  return (
    <div className="flex items-center space-x-2">
      <Loader2 className={`animate-spin text-gray-500 ${iconSize[size]}`} />
      {message && <span className="text-sm text-gray-600">{message}</span>}
    </div>
  )
}
