interface NotificationItem {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
  autoClose?: boolean
}

// Notification service interface to abstract UI store dependencies
export interface NotificationService {
  addNotification: (notification: NotificationItem) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

// Default implementation using UI store (lazy loaded to avoid circular deps)
class UIStoreNotificationService implements NotificationService {
  private _useUIStore: any

  private get useUIStore() {
    if (!this._useUIStore) {
      // Lazy import to avoid circular dependencies
      this._useUIStore = require('../stores/ui-store').useUIStore
    }
    return this._useUIStore
  }

  addNotification(notification: NotificationItem): void {
    this.useUIStore.getState().addNotification(notification)
  }

  removeNotification(id: string): void {
    this.useUIStore.getState().removeNotification(id)
  }

  clearNotifications(): void {
    this.useUIStore.getState().clearNotifications()
  }
}

// Singleton instance
let notificationService: NotificationService

export function getNotificationService(): NotificationService {
  if (!notificationService) {
    notificationService = new UIStoreNotificationService()
  }
  return notificationService
}

// Helper hook for easy access in components
export function useNotificationService() {
  return getNotificationService()
}

// For testing: allow setting a custom notification service
export function setNotificationService(service: NotificationService) {
  notificationService = service
}