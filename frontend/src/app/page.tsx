'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Suspense } from 'react'
import {
  BarChart3,
  Clock,
  Package,
  Users,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Settings,
} from 'lucide-react'
import { useJobStats } from '@/features/scheduling/hooks/use-jobs'
import {
  ManufacturingLoadingState,
  CardGridLoadingSkeleton,
} from '@/shared/components/loading-states'
import Link from 'next/link'
import type { UrlObject } from 'url'

function ManufacturingMetrics() {
  const { data: jobStats, isLoading, error } = useJobStats()

  if (isLoading) {
    return <ManufacturingLoadingState type="jobs" message="Loading production metrics..." />
  }

  if (error) {
    return (
      <div className="p-8 text-center text-red-600">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8" />
        <p>Failed to load production metrics</p>
        <Button variant="outline" size="sm" className="mt-2">
          Retry
        </Button>
      </div>
    )
  }

  const metrics = [
    {
      title: 'Active Jobs',
      value: jobStats?.['activeCount'] || 0,
      icon: Package,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
      description: 'Jobs currently in production',
      change: '+5%',
    },
    {
      title: 'Completed Today',
      value: jobStats?.['completedToday'] || 0,
      icon: TrendingUp,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
      description: 'Jobs finished today',
      change: '+12%',
    },
    {
      title: 'Scheduled',
      value: jobStats?.['scheduledCount'] || 0,
      icon: Calendar,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
      description: 'Jobs ready for production',
      change: '+3%',
    },
    {
      title: 'Overdue',
      value: jobStats?.['overdueCount'] || 0,
      icon: AlertTriangle,
      color: 'text-red-600',
      bgColor: 'bg-red-100',
      description: 'Jobs past due date',
      change: '-2%',
    },
  ]

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon
        return (
          <Card key={metric.title} className="transition-shadow hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">{metric.title}</CardTitle>
              <div className={`rounded-lg p-2 ${metric.bgColor}`}>
                <Icon className={`h-4 w-4 ${metric.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metric.value}</div>
              <div className="mt-1 flex items-center justify-between">
                <p className="text-xs text-gray-600">{metric.description}</p>
                <Badge
                  variant={metric.change.startsWith('+') ? 'default' : 'destructive'}
                  className="text-xs"
                >
                  {metric.change}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function QuickActions() {
  const actions: { title: string; description: string; href: UrlObject; icon: React.ComponentType<{ className?: string }>; color: string; bgColor: string }[] = [
    {
      title: 'Create New Job',
      description: 'Start a new production order',
      href: { pathname: '/planning' },
      icon: Package,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 hover:bg-blue-100',
    },
    {
      title: 'Schedule Resources',
      description: 'Optimize production schedule',
      href: { pathname: '/scheduling' },
      icon: BarChart3,
      color: 'text-green-600',
      bgColor: 'bg-green-50 hover:bg-green-100',
    },
    {
      title: 'Monitor Production',
      description: 'Real-time production status',
      href: { pathname: '/monitoring' },
      icon: Clock,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50 hover:bg-yellow-100',
    },
    {
      title: 'Manage Resources',
      description: 'Configure machines and operators',
      href: { pathname: '/resources' },
      icon: Users,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50 hover:bg-purple-100',
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {actions.map((action) => {
        const Icon = action.icon
        return (
          <Link key={action.title} href={action.href}>
            <Card
              className={`cursor-pointer transition-all duration-200 ${action.bgColor} border-0`}
            >
              <CardContent className="p-6">
                <div className="flex items-center space-x-4">
                  <div className="rounded-lg bg-white p-3 shadow-sm">
                    <Icon className={`h-6 w-6 ${action.color}`} />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">{action.title}</h3>
                    <p className="mt-1 text-sm text-gray-600">{action.description}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        )
      })}
    </div>
  )
}

function SystemStatus() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            System Health
            <div className="flex items-center space-x-2">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm text-green-600">Operational</span>
            </div>
          </CardTitle>
          <CardDescription>Manufacturing system status and alerts</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg bg-green-50 p-3">
            <div className="flex items-center space-x-3">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium">Database Connection</span>
            </div>
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Online
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-green-50 p-3">
            <div className="flex items-center space-x-3">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium">Scheduling Engine</span>
            </div>
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Running
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-yellow-50 p-3">
            <div className="flex items-center space-x-3">
              <div className="h-2 w-2 rounded-full bg-yellow-500" />
              <span className="text-sm font-medium">Task Domain</span>
            </div>
            <Badge variant="outline" className="bg-yellow-100 text-yellow-800">
              Limited
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest production events and updates</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start space-x-3 text-sm">
            <div className="mt-2 h-2 w-2 rounded-full bg-blue-500" />
            <div>
              <p className="font-medium">Job JOB-2025-001 created</p>
              <p className="text-gray-600">Production order for laser assembly</p>
              <p className="text-xs text-gray-500">2 minutes ago</p>
            </div>
          </div>
          <div className="flex items-start space-x-3 text-sm">
            <div className="mt-2 h-2 w-2 rounded-full bg-green-500" />
            <div>
              <p className="font-medium">Task completed on WorkCell-A</p>
              <p className="text-gray-600">Assembly task finished ahead of schedule</p>
              <p className="text-xs text-gray-500">15 minutes ago</p>
            </div>
          </div>
          <div className="flex items-start space-x-3 text-sm">
            <div className="mt-2 h-2 w-2 rounded-full bg-yellow-500" />
            <div>
              <p className="font-medium">Schedule optimization completed</p>
              <p className="text-gray-600">Weekly production schedule updated</p>
              <p className="text-xs text-gray-500">1 hour ago</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function HomePage() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Manufacturing Dashboard</h1>
          <p className="mt-1 text-gray-600">Real-time production overview and system status</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="text-sm text-gray-600">
            Last updated: {new Date().toLocaleTimeString()}
          </div>
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </div>
      </div>

      {/* Manufacturing Metrics */}
      <Suspense fallback={<CardGridLoadingSkeleton count={4} columns={4} />}>
        <ManufacturingMetrics />
      </Suspense>

      {/* Quick Actions */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Quick Actions</h2>
        <QuickActions />
      </div>

      {/* System Status */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">System Status</h2>
        <SystemStatus />
      </div>
    </div>
  )
}
