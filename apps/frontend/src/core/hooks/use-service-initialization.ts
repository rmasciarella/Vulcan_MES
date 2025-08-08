import { useEffect, useState } from 'react'
import { ServiceInitializer, isServicesInitialized } from '@/core/initialization/service-initializer'
import { logger } from '@/shared/lib/logger'

/**
 * Hook to track service initialization status
 * Useful for components that depend on services being ready
 */
export function useServiceInitialization() {
  const [isInitialized, setIsInitialized] = useState(isServicesInitialized())
  const [isInitializing, setIsInitializing] = useState(ServiceInitializer.isServicesInitializing())

  useEffect(() => {
    // Check initial state
    setIsInitialized(isServicesInitialized())
    setIsInitializing(ServiceInitializer.isServicesInitializing())

    // If not initialized, set up a polling check
    // This is lightweight since ServiceInitializer uses static flags
    const checkInterval = setInterval(() => {
      const initialized = isServicesInitialized()
      const initializing = ServiceInitializer.isServicesInitializing()
      
      setIsInitialized(initialized)
      setIsInitializing(initializing)

      // Stop polling once initialized
      if (initialized) {
        clearInterval(checkInterval)
        logger.debug('[useServiceInitialization] Services initialization detected')
      }
    }, 100) // Check every 100ms until initialized

    return () => {
      clearInterval(checkInterval)
    }
  }, [])

  return {
    isInitialized,
    isInitializing,
    isReady: isInitialized && !isInitializing
  }
}

/**
 * Hook to warm up a specific service on component mount
 * Useful for components that will definitely need a particular service
 */
export function useServiceWarmup(serviceName: 'schedule' | 'operator' | 'machine', enabled = true) {
  useEffect(() => {
    if (!enabled) return

    const warmUpService = async () => {
      try {
        await ServiceInitializer.warmUpService(serviceName)
      } catch (error) {
        logger.warn(`[useServiceWarmup] Failed to warm up ${serviceName} service:`, String(error))
      }
    }

    // Small delay to ensure services are initialized first
    const timer = setTimeout(warmUpService, 50)

    return () => {
      clearTimeout(timer)
    }
  }, [serviceName, enabled])
}