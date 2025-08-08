import type { QueryClient } from '@tanstack/react-query'

interface JobEventSubscription {
  subscriptionIds: string[]
}

let isInitialized = false
let currentSubscriptions: string[] = []

export function initializeJobEventHandlers(queryClient: QueryClient): JobEventSubscription {
  // Prevent multiple initialization
  if (isInitialized) {
    console.debug('[JobEventHandlers] Already initialized, returning existing subscriptions')
    return { subscriptionIds: currentSubscriptions }
  }

  try {
    // TODO: Wire up real-time job event subscriptions here
    // For now, just mark as initialized to prevent multiple calls
    isInitialized = true
    currentSubscriptions = [] // Will contain actual subscription IDs when implemented

    console.debug('[JobEventHandlers] Initialized successfully')
    return { subscriptionIds: currentSubscriptions }
  } catch (error) {
    console.error('[JobEventHandlers] Failed to initialize:', error)
    isInitialized = false
    throw error
  }
}

export function cleanupJobEventHandlers(subscriptionIds: string[]): void {
  if (!isInitialized) {
    return
  }

  try {
    // TODO: Clean up actual subscriptions when implemented
    // For now, just reset the state
    isInitialized = false
    currentSubscriptions = []

    console.debug('[JobEventHandlers] Cleanup completed for', subscriptionIds.length, 'subscriptions')
  } catch (error) {
    console.error('[JobEventHandlers] Failed to cleanup:', error)
  }
}
