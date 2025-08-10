'use client'

import dynamic from 'next/dynamic'
import { Skeleton } from '@/shared/ui/skeleton'

// Thin shell that lazy-loads the heavy implementation on the client only
const ResourceUtilizationChartInner = dynamic(
  () => import('./resource-utilization-chart.inner').then(m => m.ResourceUtilizationChartInner),
  { ssr: false, loading: () => <Skeleton className="h-80 w-full" /> }
)

export { type ResourceUtilizationChartProps } from './resource-utilization-chart.inner'

export function ResourceUtilizationChart(
  props: import('./resource-utilization-chart.inner').ResourceUtilizationChartProps,
) {
  return <ResourceUtilizationChartInner {...props} />
}
