import React from 'react'
import { cn } from '@/shared/lib/utils'

type SkeletonProps = {
  className?: string
  style?: React.CSSProperties
}

export function Skeleton({ className, style }: SkeletonProps) {
  return <div className={cn('animate-pulse rounded-md bg-gray-200', className)} style={style} />
}
