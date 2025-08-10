import { Info, FileText, Clock, Activity } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

type TabId = 'overview' | 'tasks' | 'timeline' | 'logs'

interface Tab {
  id: TabId
  label: string
  icon: React.ComponentType<any>
  count?: number
}

interface JobNavigationTabsProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  tasksCount?: number
}

/**
 * Job Navigation Tabs Component
 * Handles tab navigation for job details sections
 */
export function JobNavigationTabs({ activeTab, onTabChange, tasksCount }: JobNavigationTabsProps) {
  const tabs: Tab[] = [
    { id: 'overview', label: 'Overview', icon: Info },
    { 
      id: 'tasks', 
      label: 'Tasks', 
      icon: FileText, 
      ...(tasksCount !== undefined && { count: tasksCount }) 
    },
    { id: 'timeline', label: 'Timeline', icon: Clock },
    { id: 'logs', label: 'Logs', icon: Activity },
  ]

  return (
    <div className="mb-6 border-b border-gray-200">
      <nav className="flex space-x-8">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              'flex items-center border-b-2 px-1 py-2 text-sm font-medium',
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
            )}
          >
            <tab.icon className="mr-2 h-4 w-4" />
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-900">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  )
}