'use client'

import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

interface VirtualizedTableProps<T> {
  data: T[]
  renderRow: (item: T, index: number) => React.ReactNode
  estimateRowHeight?: number
  overscan?: number
  className?: string
}

export function VirtualizedTable<T>({
  data,
  renderRow,
  estimateRowHeight = 50,
  overscan = 20,
  className = '',
}: VirtualizedTableProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateRowHeight,
    overscan,
  })

  return (
    <div ref={parentRef} className={`h-full overflow-auto ${className}`}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {data[virtualItem.index] !== undefined && renderRow(data[virtualItem.index]!, virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  )
}
