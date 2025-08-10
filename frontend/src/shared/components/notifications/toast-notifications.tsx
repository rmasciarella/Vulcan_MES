'use client'

import { useEffect } from 'react'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { useUIStore } from '@/core/stores/ui-store'
import { cn } from '@/shared/lib/utils'

const notificationIcons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const notificationStyles = {
  success: {
    container: 'bg-green-50 border-green-200',
    icon: 'text-green-600',
    title: 'text-green-900',
    message: 'text-green-700',
  },
  error: {
    container: 'bg-red-50 border-red-200',
    icon: 'text-red-600',
    title: 'text-red-900',
    message: 'text-red-700',
  },
  warning: {
    container: 'bg-yellow-50 border-yellow-200',
    icon: 'text-yellow-600',
    title: 'text-yellow-900',
    message: 'text-yellow-700',
  },
  info: {
    container: 'bg-blue-50 border-blue-200',
    icon: 'text-blue-600',
    title: 'text-blue-900',
    message: 'text-blue-700',
  },
}

export function ToastNotifications() {
  const { notifications, removeNotification } = useUIStore()

  return (
    <div className="fixed right-4 top-4 z-50 w-80 space-y-2">
      {notifications.map((notification) => {
        const Icon = notificationIcons[notification.type]
        const styles = notificationStyles[notification.type]

        return (
          <div
            key={notification.id}
            className={cn(
              'relative transform rounded-lg border p-4 shadow-lg transition-all duration-300 ease-in-out animate-in slide-in-from-right-full',
              styles.container,
            )}
          >
            <div className="flex items-start space-x-3">
              <Icon className={cn('mt-0.5 h-5 w-5 flex-shrink-0', styles.icon)} />
              <div className="min-w-0 flex-1">
                <h4 className={cn('text-sm font-medium', styles.title)}>{notification.title}</h4>
                {notification.message && (
                  <p className={cn('mt-1 text-sm', styles.message)}>{notification.message}</p>
                )}
                <p className="mt-1 text-xs text-gray-500">
                  {notification.timestamp.toLocaleTimeString()}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 hover:bg-black/10"
                onClick={() => removeNotification(notification.id)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Manufacturing context badge */}
            {notification.type === 'error' && (
              <div className="mt-2 border-t border-red-200 pt-2">
                <div className="flex items-center text-xs text-red-600">
                  <AlertTriangle className="mr-1 h-3 w-3" />
                  Production Impact: Review immediately
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function GlobalNotifications() {
  const notifications = useUIStore((state) => state.notifications)

  // Auto-remove notifications after 5 seconds
  useEffect(() => {
    notifications.forEach((notification) => {
      if (notification.autoClose !== false) {
        const timer = setTimeout(() => {
          useUIStore.getState().removeNotification(notification.id)
        }, 5000)

        return () => clearTimeout(timer)
      }
    })
  }, [notifications])

  return <ToastNotifications />
}
