import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface NotificationItem {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
  timestamp: Date
  autoClose?: boolean
}

interface UIState {
  // Sidebar state
  isSidebarOpen: boolean
  isMobileMenuOpen: boolean

  // Notifications
  notifications: NotificationItem[]

  // Loading states
  isGlobalLoading: boolean
  loadingMessage?: string

  // Modal states
  activeModal: string | null
  modalData: Record<string, unknown> | null

  // Actions
  toggleSidebar: () => void
  toggleMobileMenu: () => void
  setGlobalLoading: (loading: boolean, message?: string) => void

  // Notification actions
  addNotification: (notification: Omit<NotificationItem, 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void

  // Modal actions
  openModal: (modalId: string, data?: Record<string, unknown>) => void
  closeModal: () => void
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
      // Initial state
      isSidebarOpen: true,
      isMobileMenuOpen: false,
      notifications: [],
      isGlobalLoading: false,
      activeModal: null,
      modalData: null,

      // Actions
      toggleSidebar: () =>
        set((state) => ({
          isSidebarOpen: !state.isSidebarOpen,
        })),

      toggleMobileMenu: () =>
        set((state) => ({
          isMobileMenuOpen: !state.isMobileMenuOpen,
        })),

      setGlobalLoading: (loading, message) =>
        set({
          isGlobalLoading: loading,
          loadingMessage: message ?? null as unknown as string,
        }),

      // Notification actions
      addNotification: (notification) => {
        const id = `notification-${Date.now()}`
        const newNotification: NotificationItem = {
          ...notification,
          id,
          timestamp: new Date(),
        }

        set((state) => ({
          notifications: [...state.notifications, newNotification],
        }))

        // Auto-remove after 5 seconds if autoClose is true
        if (notification.autoClose !== false) {
          setTimeout(() => {
            set((state) => ({
              notifications: state.notifications.filter((n) => n.id !== id),
            }))
          }, 5000)
        }
      },

      removeNotification: (id) =>
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        })),

      clearNotifications: () => set({ notifications: [] }),

      // Modal actions
      openModal: (modalId, data) =>
        set({
          activeModal: modalId,
          modalData: data ?? null,
        }),

      closeModal: () =>
        set({
          activeModal: null,
          modalData: null,
        }),
      }),
      {
        name: 'vulcan-ui-store',
        partialize: (state) => ({
          isSidebarOpen: state.isSidebarOpen,
          // Don't persist notifications, modal states, or loading states
        }),
      },
    ),
    {
      name: 'UIStore',
    },
  ),
)
