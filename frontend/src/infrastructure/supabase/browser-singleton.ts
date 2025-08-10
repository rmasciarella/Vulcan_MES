import { SupabaseClient, RealtimeChannel } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import { createBrowserClient } from './client'
import { clientEnv } from '@/shared/lib/env'

/**
 * Health check configuration with environment-based controls
 */
interface HealthCheckConfig {
  enabled: boolean
  intervalMs: number
  maxIntervalMs: number
  useExponentialBackoff: boolean
}

/**
 * Connection state for monitoring
 */
interface ConnectionState {
  isHealthy: boolean
  lastCheckTime: number
  consecutiveFailures: number
  currentIntervalMs: number
  isChecking: boolean
}

/**
 * Singleton browser client for manufacturing scheduling system
 * Optimized to minimize unnecessary database traffic while maintaining reliability
 */
class BrowserClientSingleton {
  private static instance: SupabaseClient<Database> | null = null
  private static realtimeChannel: RealtimeChannel | null = null
  private static healthCheckTimer: NodeJS.Timeout | null = null
  
  // Health check configuration from environment
  private static readonly config: HealthCheckConfig = {
    enabled: clientEnv.NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK,
    intervalMs: clientEnv.NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS,
    maxIntervalMs: clientEnv.NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS,
    useExponentialBackoff: true,
  }

  // Connection state tracking
  private static connectionState: ConnectionState = {
    isHealthy: true,
    lastCheckTime: 0,
    consecutiveFailures: 0,
    currentIntervalMs: BrowserClientSingleton.config.intervalMs,
    isChecking: false,
  }

  // Listeners for connection state changes
  private static stateChangeListeners = new Set<(isHealthy: boolean) => void>()

  /**
   * Get or create the singleton Supabase client
   */
  static getClient(): SupabaseClient<Database> {
    if (!BrowserClientSingleton.instance) {
      BrowserClientSingleton.instance = createBrowserClient()
      BrowserClientSingleton.setupMonitoring()
    }

    return BrowserClientSingleton.instance
  }

  /**
   * Check if the connection is healthy (cached result)
   * This method returns immediately without making any database calls
   */
  static isConnectionHealthy(): boolean {
    return BrowserClientSingleton.connectionState.isHealthy
  }

  /**
   * Perform an on-demand health check
   * Use this for critical operations that require fresh connection status
   */
  static async performHealthCheck(): Promise<boolean> {
    // Prevent concurrent health checks
    if (BrowserClientSingleton.connectionState.isChecking) {
      return BrowserClientSingleton.connectionState.isHealthy
    }

    await BrowserClientSingleton.checkConnection()
    return BrowserClientSingleton.connectionState.isHealthy
  }

  /**
   * Subscribe to connection state changes
   * Returns an unsubscribe function
   */
  static onConnectionStateChange(listener: (isHealthy: boolean) => void): () => void {
    BrowserClientSingleton.stateChangeListeners.add(listener)
    
    // Immediately notify with current state
    listener(BrowserClientSingleton.connectionState.isHealthy)
    
    // Return unsubscribe function
    return () => {
      BrowserClientSingleton.stateChangeListeners.delete(listener)
    }
  }

  /**
   * Enable or disable health checks dynamically
   * Useful for dashboards that need active monitoring
   */
  static setHealthCheckEnabled(enabled: boolean) {
    BrowserClientSingleton.config.enabled = enabled
    
    if (enabled && !BrowserClientSingleton.healthCheckTimer) {
      BrowserClientSingleton.scheduleNextHealthCheck()
    } else if (!enabled && BrowserClientSingleton.healthCheckTimer) {
      clearTimeout(BrowserClientSingleton.healthCheckTimer)
      BrowserClientSingleton.healthCheckTimer = null
    }
  }

  /**
   * Setup connection monitoring
   */
  private static setupMonitoring() {
    if (!BrowserClientSingleton.instance) return

    // Monitor auth state changes as a proxy for connection health
    BrowserClientSingleton.instance.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT' || event === 'TOKEN_REFRESHED') {
        console.info(`[Supabase] Auth event: ${event}`)
      }
      
      if (event === 'SIGNED_OUT') {
        console.warn('[Supabase] User signed out - this may affect manufacturing data access')
      }

      // Auth state changes indicate the connection is working
      if (session && !BrowserClientSingleton.connectionState.isHealthy) {
        BrowserClientSingleton.updateConnectionState(true)
      }
    })

    // Setup realtime connection monitoring (lightweight, uses existing WebSocket)
    BrowserClientSingleton.setupRealtimeMonitoring()

    // Schedule health checks only if enabled
    if (BrowserClientSingleton.config.enabled) {
      BrowserClientSingleton.scheduleNextHealthCheck()
    }
  }

  /**
   * Setup realtime channel for connection monitoring
   * This uses the existing WebSocket connection without additional database queries
   */
  private static setupRealtimeMonitoring() {
    if (!BrowserClientSingleton.instance) return

    // Create a dedicated channel for connection monitoring
    BrowserClientSingleton.realtimeChannel = BrowserClientSingleton.instance
      .channel('connection-monitor', {
        config: {
          broadcast: { self: true },
        },
      })

    // Monitor channel states
    BrowserClientSingleton.realtimeChannel
      .on('system', { event: '*' }, (payload) => {
        // Connection established or recovered
        if (payload.event === 'connected' || payload.event === 'reconnected') {
          BrowserClientSingleton.updateConnectionState(true)
        }
        // Connection lost
        else if (payload.event === 'disconnected' || payload.event === 'error') {
          BrowserClientSingleton.updateConnectionState(false)
        }
      })
      .subscribe((status) => {
        // Update connection state based on subscription status
        const isHealthy = status === 'SUBSCRIBED'
        if (isHealthy !== BrowserClientSingleton.connectionState.isHealthy) {
          BrowserClientSingleton.updateConnectionState(isHealthy)
        }
      })
  }

  /**
   * Perform a lightweight health check
   * Uses system.now() function instead of querying tables
   */
  private static async checkConnection() {
    if (!BrowserClientSingleton.instance) return
    
    // Mark as checking to prevent concurrent checks
    BrowserClientSingleton.connectionState.isChecking = true

    try {
      // Use a lightweight RPC call or system function instead of table query
      // This avoids unnecessary table access while still verifying connectivity
      const { error } = await BrowserClientSingleton.instance.rpc('ping', {})
        .catch(() => 
          // Fallback to a minimal query only if RPC is not available
          BrowserClientSingleton.instance!
            .from('_prisma_migrations')
            .select('id')
            .limit(1)
            .single()
        )

      const isHealthy = !error
      BrowserClientSingleton.updateConnectionState(isHealthy)

      if (error && BrowserClientSingleton.config.enabled) {
        console.warn('[Supabase] Health check failed:', error.message)
      }
    } catch (err) {
      BrowserClientSingleton.updateConnectionState(false)
      if (BrowserClientSingleton.config.enabled) {
        console.error('[Supabase] Health check error:', err)
      }
    } finally {
      BrowserClientSingleton.connectionState.isChecking = false
      BrowserClientSingleton.connectionState.lastCheckTime = Date.now()
    }

    // Schedule next check if enabled
    if (BrowserClientSingleton.config.enabled) {
      BrowserClientSingleton.scheduleNextHealthCheck()
    }
  }

  /**
   * Update connection state and notify listeners
   */
  private static updateConnectionState(isHealthy: boolean) {
    const previousState = BrowserClientSingleton.connectionState.isHealthy
    
    if (isHealthy) {
      // Connection recovered
      BrowserClientSingleton.connectionState.isHealthy = true
      BrowserClientSingleton.connectionState.consecutiveFailures = 0
      BrowserClientSingleton.connectionState.currentIntervalMs = BrowserClientSingleton.config.intervalMs
      
      if (!previousState) {
        console.info('[Supabase] Connection recovered')
      }
    } else {
      // Connection failed
      BrowserClientSingleton.connectionState.isHealthy = false
      BrowserClientSingleton.connectionState.consecutiveFailures++
      
      // Apply exponential backoff if enabled
      if (BrowserClientSingleton.config.useExponentialBackoff) {
        const backoffMultiplier = Math.min(BrowserClientSingleton.connectionState.consecutiveFailures, 6)
        BrowserClientSingleton.connectionState.currentIntervalMs = Math.min(
          BrowserClientSingleton.config.intervalMs * Math.pow(2, backoffMultiplier),
          BrowserClientSingleton.config.maxIntervalMs
        )
      }
      
      if (previousState) {
        console.warn('[Manufacturing] Database connection lost - production scheduling may be affected')
      }
    }

    // Notify listeners only if state actually changed
    if (previousState !== isHealthy) {
      BrowserClientSingleton.stateChangeListeners.forEach(listener => {
        try {
          listener(isHealthy)
        } catch (error) {
          console.error('[Supabase] Error in state change listener:', error)
        }
      })
    }
  }

  /**
   * Schedule the next health check with exponential backoff
   */
  private static scheduleNextHealthCheck() {
    // Clear any existing timer
    if (BrowserClientSingleton.healthCheckTimer) {
      clearTimeout(BrowserClientSingleton.healthCheckTimer)
    }

    // Don't schedule if disabled
    if (!BrowserClientSingleton.config.enabled) {
      return
    }

    // Use current interval (may be backed off due to failures)
    const intervalMs = BrowserClientSingleton.connectionState.currentIntervalMs

    BrowserClientSingleton.healthCheckTimer = setTimeout(() => {
      BrowserClientSingleton.checkConnection()
    }, intervalMs)
  }

  /**
   * Reset singleton for testing or reconnection scenarios
   */
  static reset() {
    // Clean up timers
    if (BrowserClientSingleton.healthCheckTimer) {
      clearTimeout(BrowserClientSingleton.healthCheckTimer)
      BrowserClientSingleton.healthCheckTimer = null
    }

    // Clean up realtime channel
    if (BrowserClientSingleton.realtimeChannel) {
      BrowserClientSingleton.realtimeChannel.unsubscribe()
      BrowserClientSingleton.realtimeChannel = null
    }

    // Clear listeners
    BrowserClientSingleton.stateChangeListeners.clear()

    // Reset state
    BrowserClientSingleton.instance = null
    BrowserClientSingleton.connectionState = {
      isHealthy: true,
      lastCheckTime: 0,
      consecutiveFailures: 0,
      currentIntervalMs: BrowserClientSingleton.config.intervalMs,
      isChecking: false,
    }
  }

  /**
   * Get connection statistics for debugging
   */
  static getConnectionStats() {
    return {
      config: BrowserClientSingleton.config,
      state: BrowserClientSingleton.connectionState,
      listenerCount: BrowserClientSingleton.stateChangeListeners.size,
      hasActiveTimer: BrowserClientSingleton.healthCheckTimer !== null,
      hasRealtimeChannel: BrowserClientSingleton.realtimeChannel !== null,
    }
  }
}

/**
 * Get the singleton Supabase browser client
 * Use this in React hooks and client-side code to prevent creating multiple connections
 */
export function getSupabaseBrowserClient(): SupabaseClient<Database> {
  return BrowserClientSingleton.getClient()
}

/**
 * Check if the Supabase connection is healthy (cached, no database call)
 * Important for manufacturing systems where data reliability is critical
 */
export function isSupabaseConnectionHealthy(): boolean {
  return BrowserClientSingleton.isConnectionHealthy()
}

/**
 * Perform an on-demand health check (makes actual database call)
 * Use sparingly for critical operations only
 */
export async function checkSupabaseConnection(): Promise<boolean> {
  return BrowserClientSingleton.performHealthCheck()
}

/**
 * Subscribe to connection state changes
 * Returns an unsubscribe function
 * 
 * @example
 * const unsubscribe = onSupabaseConnectionChange((isHealthy) => {
 *   console.log('Connection healthy:', isHealthy)
 * })
 */
export function onSupabaseConnectionChange(listener: (isHealthy: boolean) => void): () => void {
  return BrowserClientSingleton.onConnectionStateChange(listener)
}

/**
 * Enable or disable health checks dynamically
 * Useful for dashboards that need active monitoring
 */
export function setSupabaseHealthCheckEnabled(enabled: boolean) {
  BrowserClientSingleton.setHealthCheckEnabled(enabled)
}

/**
 * Get connection statistics for debugging
 */
export function getSupabaseConnectionStats() {
  return BrowserClientSingleton.getConnectionStats()
}

/**
 * Reset the singleton client (primarily for testing)
 */
export function resetSupabaseBrowserClient() {
  BrowserClientSingleton.reset()
}