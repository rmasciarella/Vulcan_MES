import React, { useMemo } from 'react'
import { Card } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Select } from '@/shared/ui/select'
import { Input } from '@/shared/ui/input'
import { Checkbox } from '@/shared/ui/checkbox'
import { Alert } from '@/shared/ui/alert'
import {
  useResourceAllocation,
  useResources,
  useUnallocatedTasks,
  useBatchAllocate,
  useOptimizeAllocation,
  useResourceConflicts,
  useResourceUtilization,
} from '../hooks/use-resource-allocation'

export function ResourceAllocationDashboard() {
  const {
    currentView,
    selectedResources,
    selectedTasks,
    filters,
    preferences,
    setView,
    setFilters,
    toggleResourceSelection,
    toggleTaskSelection,
    selectAllResources,
    selectAllTasks,
    clearResourceSelection,
    clearTaskSelection,
    updatePreferences,
  } = useResourceAllocation()

  const { resources, isLoading } = useResources()
  const unallocatedTasks = useUnallocatedTasks()
  const batchAllocateMutation = useBatchAllocate()
  const optimizeMutation = useOptimizeAllocation()
  const { conflicts, hasConflicts } = useResourceConflicts()
  const { utilizationData, overUtilizedResources, averageUtilization } = useResourceUtilization()

  const handleResourceTypeFilter = (type: string) => {
    setFilters({ 
      resourceType: type === 'all' ? 'all' : type as 'machine' | 'operator' | 'workcell' | 'all'
    })
  }

  const handleStatusFilter = (status: string) => {
    setFilters({ 
      status: status === 'all' ? 'all' : status as 'allocated' | 'available' | 'maintenance' | 'offline' | 'all'
    })
  }

  const handleSearchFilter = (search: string) => {
    setFilters({ search })
  }

  const handleUtilizationFilter = (min: string, max: string) => {
    const updates: Partial<ResourceFilters> = {}
    if (min) updates.utilizationMin = parseFloat(min)
    if (max) updates.utilizationMax = parseFloat(max)
    setFilters(updates)
  }

  const handleSelectAllResources = () => {
    const resourceIds = resources.map(r => r.id)
    selectAllResources(resourceIds)
  }

  const handleSelectAllTasks = () => {
    const taskIds = unallocatedTasks.map(t => t.id)
    selectAllTasks(taskIds)
  }

  const handleBatchAllocate = (strategy: 'auto' | 'manual') => {
    batchAllocateMutation.mutate(strategy)
  }

  const handleOptimize = () => {
    optimizeMutation.mutate({
      optimizeFor: 'utilization',
      timeHorizon: 24, // 24 hours
      respectSkills: true,
      allowReallocation: false,
    })
  }

  const resourcesByType = useMemo(() => {
    return resources.reduce((acc, resource) => {
      if (!acc[resource.type]) {
        acc[resource.type] = []
      }
      acc[resource.type].push(resource)
      return acc
    }, {} as Record<string, typeof resources>)
  }, [resources])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Resource Allocation</h1>
        <div className="flex items-center gap-2">
          <Button
            onClick={handleOptimize}
            disabled={optimizeMutation.isPending}
            variant="outline"
          >
            {optimizeMutation.isPending ? 'Optimizing...' : 'Optimize'}
          </Button>
          <Button
            onClick={() => handleBatchAllocate('auto')}
            disabled={selectedResources.length === 0 || selectedTasks.length === 0 || batchAllocateMutation.isPending}
            variant="outline"
          >
            Auto Allocate
          </Button>
          <Button
            onClick={() => handleBatchAllocate('manual')}
            disabled={selectedResources.length === 0 || selectedTasks.length === 0 || batchAllocateMutation.isPending}
          >
            {batchAllocateMutation.isPending ? 'Allocating...' : 'Manual Allocate'}
          </Button>
        </div>
      </div>

      {/* Conflicts Alert */}
      {hasConflicts && (
        <Alert variant="destructive">
          <div>
            <h3 className="font-medium mb-2">Resource Conflicts Detected</h3>
            <div className="space-y-1 text-sm">
              {conflicts.slice(0, 3).map((conflict, index) => (
                <div key={index}>
                  {conflict.description}
                </div>
              ))}
              {conflicts.length > 3 && (
                <div className="text-xs opacity-75">
                  +{conflicts.length - 3} more conflicts
                </div>
              )}
            </div>
          </div>
        </Alert>
      )}

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-600">Total Resources</div>
          <div className="text-2xl font-bold">{resources.length}</div>
          <div className="text-xs text-gray-500">
            {resourcesByType.machine?.length || 0} machines, {resourcesByType.operator?.length || 0} operators
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-600">Unallocated Tasks</div>
          <div className="text-2xl font-bold">{unallocatedTasks.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-600">Average Utilization</div>
          <div className="text-2xl font-bold">{averageUtilization.toFixed(1)}%</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-600">Over-utilized</div>
          <div className="text-2xl font-bold text-red-600">{overUtilizedResources.length}</div>
          <div className="text-xs text-gray-500">
            &gt;{preferences.showUtilizationThreshold}% utilization
          </div>
        </Card>
      </div>

      {/* Filters and Controls */}
      <Card>
        <div className="p-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            {/* View Selector */}
            <div>
              <label className="block text-sm font-medium mb-1">View</label>
              <Select
                value={currentView}
                onValueChange={(value) => setView(value as any)}
              >
                <option value="matrix">Matrix</option>
                <option value="timeline">Timeline</option>
                <option value="utilization">Utilization</option>
                <option value="capacity">Capacity</option>
              </Select>
            </div>

            {/* Resource Type Filter */}
            <div>
              <label className="block text-sm font-medium mb-1">Resource Type</label>
              <Select
                value={filters.resourceType || 'all'}
                onValueChange={handleResourceTypeFilter}
              >
                <option value="all">All Types</option>
                <option value="machine">Machines</option>
                <option value="operator">Operators</option>
                <option value="workcell">Workcells</option>
              </Select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium mb-1">Status</label>
              <Select
                value={filters.status || 'all'}
                onValueChange={handleStatusFilter}
              >
                <option value="all">All Status</option>
                <option value="available">Available</option>
                <option value="allocated">Allocated</option>
                <option value="maintenance">Maintenance</option>
                <option value="offline">Offline</option>
              </Select>
            </div>

            {/* Search */}
            <div>
              <label className="block text-sm font-medium mb-1">Search</label>
              <Input
                type="text"
                placeholder="Search resources..."
                value={filters.search || ''}
                onChange={(e) => handleSearchFilter(e.target.value)}
              />
            </div>

            {/* Utilization Range */}
            <div className="flex gap-2">
              <div>
                <label className="block text-sm font-medium mb-1">Min %</label>
                <Input
                  type="number"
                  placeholder="0"
                  min="0"
                  max="100"
                  className="w-20"
                  value={filters.utilizationMin || ''}
                  onChange={(e) => handleUtilizationFilter(e.target.value, filters.utilizationMax?.toString() || '')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Max %</label>
                <Input
                  type="number"
                  placeholder="100"
                  min="0"
                  max="100"
                  className="w-20"
                  value={filters.utilizationMax || ''}
                  onChange={(e) => handleUtilizationFilter(filters.utilizationMin?.toString() || '', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Preferences */}
          <div className="flex flex-wrap gap-4 pt-2 border-t">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="auto-allocate"
                checked={preferences.autoAllocate}
                onCheckedChange={(checked) => updatePreferences({ autoAllocate: checked as boolean })}
              />
              <label htmlFor="auto-allocate" className="text-sm">Auto Allocate</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="show-conflicts"
                checked={preferences.showConflicts}
                onCheckedChange={(checked) => updatePreferences({ showConflicts: checked as boolean })}
              />
              <label htmlFor="show-conflicts" className="text-sm">Show Conflicts</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="group-by-type"
                checked={preferences.groupByResourceType}
                onCheckedChange={(checked) => updatePreferences({ groupByResourceType: checked as boolean })}
              />
              <label htmlFor="group-by-type" className="text-sm">Group by Type</label>
            </div>
          </div>
        </div>
      </Card>

      {/* Selection Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium">Resources ({resources.length})</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">
                {selectedResources.length} selected
              </span>
              <Button variant="outline" size="sm" onClick={handleSelectAllResources}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={clearResourceSelection}>
                Clear
              </Button>
            </div>
          </div>
          
          <ResourceSelectionList 
            resources={resources}
            selectedResources={selectedResources}
            onToggleSelection={toggleResourceSelection}
            groupByType={preferences.groupByResourceType}
          />
        </Card>

        <Card className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium">Unallocated Tasks ({unallocatedTasks.length})</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">
                {selectedTasks.length} selected
              </span>
              <Button variant="outline" size="sm" onClick={handleSelectAllTasks}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={clearTaskSelection}>
                Clear
              </Button>
            </div>
          </div>
          
          <TaskSelectionList 
            tasks={unallocatedTasks}
            selectedTasks={selectedTasks}
            onToggleSelection={toggleTaskSelection}
          />
        </Card>
      </div>

      {/* Current View */}
      <Card>
        <div className="p-4">
          {currentView === 'matrix' && (
            <div className="text-center text-gray-500 py-8">
              Resource Allocation Matrix view would be implemented here
            </div>
          )}
          {currentView === 'timeline' && (
            <div className="text-center text-gray-500 py-8">
              Resource Timeline view would be implemented here
            </div>
          )}
          {currentView === 'utilization' && (
            <ResourceUtilizationView utilizationData={utilizationData} />
          )}
          {currentView === 'capacity' && (
            <div className="text-center text-gray-500 py-8">
              Capacity Planning view would be implemented here
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

// Resource selection component
function ResourceSelectionList({ 
  resources, 
  selectedResources, 
  onToggleSelection,
  groupByType 
}: {
  resources: any[]
  selectedResources: string[]
  onToggleSelection: (resourceId: string) => void
  groupByType: boolean
}) {
  if (resources.length === 0) {
    return (
      <div className="text-center text-gray-500 py-4">
        No resources found. Adjust your filters.
      </div>
    )
  }

  const organizedResources = groupByType 
    ? resources.reduce((acc, resource) => {
        if (!acc[resource.type]) acc[resource.type] = []
        acc[resource.type].push(resource)
        return acc
      }, {} as Record<string, any[]>)
    : { 'All Resources': resources }

  return (
    <div className="space-y-3 max-h-64 overflow-y-auto">
      {Object.entries(organizedResources).map(([groupName, groupResources]) => (
        <div key={groupName}>
          {groupByType && (
            <h4 className="font-medium text-sm text-gray-700 mb-2 capitalize">
              {groupName}s ({groupResources.length})
            </h4>
          )}
          <div className="space-y-1">
            {groupResources.map((resource) => {
              const isSelected = selectedResources.includes(resource.id)
              
              return (
                <div
                  key={resource.id}
                  className={`flex items-center justify-between p-2 border rounded cursor-pointer transition-colors ${
                    isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => onToggleSelection(resource.id)}
                >
                  <div className="flex items-center space-x-2">
                    <Checkbox checked={isSelected} readOnly />
                    <div>
                      <div className="font-medium text-sm">{resource.name}</div>
                      <div className="text-xs text-gray-500">
                        {resource.skills?.slice(0, 2).join(', ')} 
                        {resource.skills?.length > 2 && ` +${resource.skills.length - 2} more`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge variant={resource.status === 'available' ? 'default' : 'outline'}>
                      {resource.status}
                    </Badge>
                    <div className="text-xs text-gray-500">
                      {resource.utilization}%
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// Task selection component
function TaskSelectionList({ 
  tasks, 
  selectedTasks, 
  onToggleSelection 
}: {
  tasks: any[]
  selectedTasks: string[]
  onToggleSelection: (taskId: string) => void
}) {
  if (tasks.length === 0) {
    return (
      <div className="text-center text-gray-500 py-4">
        No unallocated tasks found.
      </div>
    )
  }

  return (
    <div className="space-y-1 max-h-64 overflow-y-auto">
      {tasks.map((task) => {
        const isSelected = selectedTasks.includes(task.id)
        
        return (
          <div
            key={task.id}
            className={`flex items-center justify-between p-2 border rounded cursor-pointer transition-colors ${
              isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
            }`}
            onClick={() => onToggleSelection(task.id)}
          >
            <div className="flex items-center space-x-2">
              <Checkbox checked={isSelected} readOnly />
              <div>
                <div className="font-medium text-sm">{task.name}</div>
                <div className="text-xs text-gray-500">
                  Job: {task.jobName} • {task.estimatedDuration}min
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant={task.priority > 3 ? 'destructive' : 'outline'}>
                Priority {task.priority}
              </Badge>
              {task.requiredSkills.length > 0 && (
                <div className="text-xs text-gray-500">
                  Skills: {task.requiredSkills.slice(0, 2).join(', ')}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Resource utilization view component
function ResourceUtilizationView({ utilizationData }: { utilizationData: any[] }) {
  if (utilizationData.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        No utilization data available. Set a date range in filters.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="font-medium">Resource Utilization</h3>
      <div className="space-y-2">
        {utilizationData.map((data) => (
          <div key={data.resourceId} className="flex items-center justify-between p-3 border rounded">
            <div>
              <div className="font-medium">{data.resourceName}</div>
              <div className="text-sm text-gray-500 capitalize">
                {data.resourceType} • {data.allocationCount} allocations
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="text-right">
                <div className="text-sm">
                  {data.allocatedHours.toFixed(1)}h / {(data.allocatedHours + data.availableHours).toFixed(1)}h
                </div>
                <div className="text-xs text-gray-500">
                  {data.availableHours.toFixed(1)}h available
                </div>
              </div>
              <div className="w-24 bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    data.utilization > 80 ? 'bg-red-500' : 
                    data.utilization > 60 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(data.utilization, 100)}%` }}
                />
              </div>
              <div className="text-sm font-medium min-w-[3rem] text-right">
                {data.utilization.toFixed(1)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}