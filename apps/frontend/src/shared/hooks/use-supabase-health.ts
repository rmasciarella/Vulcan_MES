import React, { useEffect, useState, useCallback } from 'react'
import { 
  isSupabaseConnectionHealthy, 
  onSupabaseConnectionChange,
  setSupabaseHealthCheckEnabled,
  checkSupabaseConnection,
  getSupabaseConnectionStats
} from '@/infrastructure/supabase/browser-singleton'

/**
 * Options for the Supabase health monitoring hook
 */
interface UseSupabaseHealthOptions {
  /**
   * Enable active health checks for this component
   * When true, enables periodic health checks while the component is mounted
   * @default false
   */
  enableActiveMonitoring?: boolean
  
  /**
   * Callback when connection state changes
   */
  onConnectionChange?: (isHealthy: boolean) => void
  
  /**
   * Perform an initial health check on mount
   * @default false
   */
  checkOnMount?: boolean
}

/**
 * Hook for monitoring Supabase connection health
 * 
 * @example
 * // Basic usage - just get connection status
 * const { isHealthy } = useSupabaseHealth()
 * 
 * @example
 * // Enable active monitoring for critical dashboards
 * const { isHealthy, checkNow } = useSupabaseHealth({
 *   enableActiveMonitoring: true,
 *   onConnectionChange: (healthy) => {
 *     if (!healthy) {
 *       toast.error('Database connection lost')
 *     }
 *   }
 * })
 */
export function useSupabaseHealth(options: UseSupabaseHealthOptions = {}) {
  const {
    enableActiveMonitoring = false,
    onConnectionChange,
    checkOnMount = false
  } = options

  const [isHealthy, setIsHealthy] = useState(isSupabaseConnectionHealthy())
  const [isChecking, setIsChecking] = useState(false)
  const [lastCheckTime, setLastCheckTime] = useState<Date | null>(null)

  // Perform an on-demand health check
  const checkNow = useCallback(async () => {
    setIsChecking(true)
    try {
      const healthy = await checkSupabaseConnection()
      setIsHealthy(healthy)
      setLastCheckTime(new Date())
      return healthy
    } finally {
      setIsChecking(false)
    }
  }, [])

  // Get detailed connection statistics
  const getStats = useCallback(() => {
    return getSupabaseConnectionStats()
  }, [])

  useEffect(() => {
    // Subscribe to connection state changes
    const unsubscribe = onSupabaseConnectionChange((healthy) => {
      setIsHealthy(healthy)
      onConnectionChange?.(healthy)
    })

    // Enable active monitoring if requested
    if (enableActiveMonitoring) {
      setSupabaseHealthCheckEnabled(true)
    }

    // Perform initial check if requested
    if (checkOnMount) {
      checkNow()
    }

    // Cleanup
    return () => {
      unsubscribe()
      
      // Note: We don't disable health checks on unmount because
      // other components might need them. The singleton manages
      // the global state appropriately.
    }
  }, [enableActiveMonitoring, checkOnMount]) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    /**
     * Current connection health status (cached)
     */
    isHealthy,
    
    /**
     * Whether a health check is currently in progress
     */
    isChecking,
    
    /**
     * Timestamp of the last health check
     */
    lastCheckTime,
    
    /**
     * Perform an on-demand health check
     */
    checkNow,
    
    /**
     * Get detailed connection statistics
     */
    getStats,
    
    /**
     * Enable or disable health checks globally
     */
    setHealthCheckEnabled: setSupabaseHealthCheckEnabled
  }
}

/**
 * Higher-order component that provides connection health monitoring
 * Useful for wrapping critical components that need database access
 * 
 * @example
 * const MonitoredDashboard = withSupabaseHealthMonitoring(Dashboard, {
 *   enableActiveMonitoring: true,
 *   fallback: <ConnectionLostMessage />
 * })
 */
export function withSupabaseHealthMonitoring<P extends object>(
  Component: React.ComponentType<P & { isSupabaseHealthy: boolean }>,
  options?: UseSupabaseHealthOptions & { 
    fallback?: React.ReactNode 
  }
) {
  return function WrappedComponent(props: P) {
    const { isHealthy } = useSupabaseHealth(options)
    
    if (!isHealthy && options?.fallback) {
      return React.createElement(React.Fragment, null, options.fallback)
    }
    
    return React.createElement(Component, { ...props, isSupabaseHealthy: isHealthy } as P & { isSupabaseHealthy: boolean })
  }
}