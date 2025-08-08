import React from 'react'

type Row = {
  instance_id: string
  name: string
  description?: string | null
  status: string
  due_date?: string | null
}

export function VirtualizedJobTable({ 
  jobs, 
  height, 
  onJobClick, 
  onStatusChange 
}: { 
  jobs: Row[]
  height?: number
  onJobClick?: (job: Row) => void
  onStatusChange?: (jobId: string, status: string) => void 
}) {
  // Minimal, non-virtualized placeholder table to unblock build
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-auto border-collapse">
        <thead>
          <tr className="bg-gray-50 text-left text-sm text-gray-600">
            <th className="px-4 py-2">ID</th>
            <th className="px-4 py-2">Name</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Due</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr 
              key={j.instance_id} 
              className="border-b cursor-pointer hover:bg-gray-50"
              onClick={() => onJobClick?.(j)}
            >
              <td className="px-4 py-2 text-sm text-gray-700">{j.instance_id}</td>
              <td className="px-4 py-2 text-sm text-gray-900">{j.name}</td>
              <td className="px-4 py-2 text-sm">
                <button 
                  onClick={(e) => {
                    e.stopPropagation()
                    onStatusChange?.(j.instance_id, j.status)
                  }}
                  className="text-left hover:text-blue-600"
                >
                  {j.status}
                </button>
              </td>
              <td className="px-4 py-2 text-sm">{j.due_date ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
