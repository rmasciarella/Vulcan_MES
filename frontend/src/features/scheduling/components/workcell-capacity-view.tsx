'use client'

import dynamic from 'next/dynamic'
import { Skeleton } from '@/shared/ui/skeleton'

const WorkCellCapacityViewInner = dynamic(
  () => import('./workcell-capacity-view.inner').then(m => m.WorkCellCapacityViewInner),
  { ssr: false, loading: () => <Skeleton className="h-[600px] w-full" /> }
)

export { type WorkCellCapacityViewProps } from './workcell-capacity-view.inner'

export function WorkCellCapacityView(
  props: import('./workcell-capacity-view.inner').WorkCellCapacityViewProps,
) {
  return <WorkCellCapacityViewInner {...props} />
}
