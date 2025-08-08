'use client'

import { useState } from 'react'
import {
  Menu,
  X,
  Home,
  Calendar,
  Settings,
  BarChart3,
  Users,
  Package,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { useUIStore } from '@/core/stores/ui-store'
import { cn } from '@/shared/lib/utils'
import { env } from '@/shared/lib/env'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface NavigationItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: number
  description: string
}

const navigation: NavigationItem[] = [
  {
    name: 'Dashboard',
    href: '/',
    icon: Home,
    description: 'Manufacturing overview and KPIs',
  },
  {
    name: 'Planning',
    href: '/planning',
    icon: Calendar,
    description: 'Production planning and job management',
  },
  {
    name: 'Scheduling',
    href: '/scheduling',
    icon: BarChart3,
    description: 'Resource allocation and task scheduling',
  },
  {
    name: 'Resources',
    href: '/resources',
    icon: Users,
    description: 'Machines, operators, and work cells',
  },
  {
    name: 'Jobs',
    href: '/jobs',
    icon: Package,
    description: 'Production orders and workflow',
  },
  {
    name: 'Monitoring',
    href: '/monitoring',
    icon: AlertTriangle,
    description: 'Real-time system monitoring',
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
    description: 'System configuration and preferences',
  },
]

function DevHealthBanner() {
  if (typeof window === 'undefined') return null
  if (process.env.NODE_ENV === 'production') return null
  const usingMock = env.NEXT_PUBLIC_ENABLE_MOCK_DATA
  const missingSupabase = !env.NEXT_PUBLIC_SUPABASE_URL || !env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!usingMock && !missingSupabase) return null
  return (
    <div className="w-full bg-amber-100 text-amber-900 px-4 py-2 text-sm flex items-center gap-3">
      <span>Dev notice:</span>
      {usingMock ? <span>Mock data mode is enabled.</span> : null}
      {missingSupabase ? <span>Supabase env incomplete.</span> : null}
      <Link className="underline" href="/api/health" target="_blank" rel="noreferrer">
        /api/health
      </Link>
    </div>
  )
}

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()
  const { isSidebarOpen, toggleSidebar } = useUIStore()
  const [isMobileOpen, setIsMobileOpen] = useState(false)

  const isActiveRoute = (href: string) => {
    if (href === '/') {
      return pathname === '/'
    }
    return pathname.startsWith(href)
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 transform border-r border-gray-200 bg-white transition-transform duration-200 ease-in-out lg:static',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
          !isSidebarOpen && 'lg:-translate-x-full',
        )}
      >
        <div className="flex h-full flex-col">
          {/* Logo/Header */}
          <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
            <div className="flex items-center space-x-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
                <Package className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">Vulcan MES</h1>
                <p className="text-xs text-gray-500">Manufacturing System</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={() => setIsMobileOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-4">
            {navigation.map((item) => {
              const isActive = isActiveRoute(item.href)
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    'group flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'border border-blue-200 bg-blue-100 text-blue-900'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900',
                  )}
                  onClick={() => setIsMobileOpen(false)}
                >
                  <item.icon
                    className={cn(
                      'mr-3 h-5 w-5 flex-shrink-0',
                      isActive ? 'text-blue-600' : 'text-gray-400 group-hover:text-gray-600',
                    )}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span>{item.name}</span>
                      {item.badge && (
                        <Badge variant="secondary" className="ml-2 text-xs">
                          {item.badge}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-gray-500 group-hover:text-gray-600">
                      {item.description}
                    </p>
                  </div>
                </Link>
              )
            })}
          </nav>

          {/* Footer */}
          <div className="border-t border-gray-200 px-4 py-4">
            <div className="text-xs text-gray-500">
              <div className="flex items-center justify-between">
                <span>System Status</span>
                <div className="flex items-center space-x-1">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                  <span className="text-green-600">Online</span>
                </div>
              </div>
              <div className="mt-1 text-gray-400">
                Last updated: {new Date().toLocaleTimeString()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <DevHealthBanner />
        {/* Top header */}
        <header className="border-b border-gray-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (window.innerWidth >= 1024) {
                    toggleSidebar()
                  } else {
                    setIsMobileOpen(true)
                  }
                }}
              >
                <Menu className="h-4 w-4" />
              </Button>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {navigation.find((nav) => isActiveRoute(nav.href))?.name || 'Dashboard'}
                </h2>
                <p className="text-sm text-gray-500">
                  {navigation.find((nav) => isActiveRoute(nav.href))?.description ||
                    'Manufacturing overview'}
                </p>
              </div>
            </div>

            {/* Quick actions */}
            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm">
                Refresh Data
              </Button>
              <div className="flex items-center space-x-2 rounded-lg bg-gray-100 px-3 py-1">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm text-gray-700">Real-time</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
