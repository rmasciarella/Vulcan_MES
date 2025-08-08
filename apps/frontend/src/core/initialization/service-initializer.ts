import { UseCaseFactory } from '@/core/use-cases/use-case-factory'
import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import { logger } from '@/shared/lib/logger'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '../../../types/supabase'

/**
 * Service initialization manager with performance optimizations
 * Handles idempotent initialization of core services and prevents duplicate calls
 */
class ServiceInitializer {
  private static instance: ServiceInitializer | null = null
  private static initializationPromise: Promise<void> | null = null
  private static isInitialized = false
  private static isInitializing = false

  private constructor() {}

  /**
   * Get singleton instance
   */
  static getInstance(): ServiceInitializer {
    if (!ServiceInitializer.instance) {
      ServiceInitializer.instance = new ServiceInitializer()
    }
    return ServiceInitializer.instance
  }

  /**
   * Initialize all core services (idempotent)
   * Safe to call multiple times - will only initialize once
   */
  static async initializeServices(options?: {
    supabaseClient?: SupabaseClient<Database>
    preWarm?: boolean
  }): Promise<void> {
    // Return immediately if already initialized
    if (ServiceInitializer.isInitialized) {
      logger.debug('[ServiceInitializer] Services already initialized')
      return
    }

    // If currently initializing, wait for completion
    if (ServiceInitializer.isInitializing && ServiceInitializer.initializationPromise) {
      logger.debug('[ServiceInitializer] Initialization in progress, waiting...')
      await ServiceInitializer.initializationPromise
      return
    }

    // Mark as initializing and create promise
    ServiceInitializer.isInitializing = true
    ServiceInitializer.initializationPromise = ServiceInitializer._performInitialization(options)

    try {
      await ServiceInitializer.initializationPromise
      ServiceInitializer.isInitialized = true
      logger.debug('[ServiceInitializer] All services initialized successfully')
    } catch (error) {
      ServiceInitializer.isInitializing = false
      ServiceInitializer.initializationPromise = null
      logger.error('[ServiceInitializer] Service initialization failed:', String(error))
      throw error
    } finally {
      ServiceInitializer.isInitializing = false
    }
  }

  /**
   * Internal initialization logic
   */
  private static async _performInitialization(options?: {
    supabaseClient?: SupabaseClient<Database>
    preWarm?: boolean
  }): Promise<void> {
    const { supabaseClient, preWarm = true } = options || {}

    try {
      // Initialize UseCaseFactory
      const client = supabaseClient || getSupabaseBrowserClient()
      await UseCaseFactory.initialize(client)

      // Pre-warm commonly used services if requested
      if (preWarm) {
        await ServiceInitializer._preWarmServices()
      }

      logger.debug('[ServiceInitializer] Core services initialized')
    } catch (error) {
      logger.error('[ServiceInitializer] Failed to initialize core services:', String(error))
      throw error
    }
  }

  /**
   * Pre-warm commonly used services to improve first-load performance
   */
  private static async _preWarmServices(): Promise<void> {
    try {
      const factory = UseCaseFactory.getInstance()
      
      // Pre-warm schedule services (most commonly used)
      await factory.getScheduleUseCases()
      
      // Pre-warm operator services in the background
      // Using setTimeout to avoid blocking the main initialization
      setTimeout(async () => {
        try {
          await factory.getOperatorUseCases()
          await factory.getMachineUseCases()
          logger.debug('[ServiceInitializer] Background pre-warming completed')
        } catch (error) {
          logger.warn('[ServiceInitializer] Background pre-warming failed:', String(error))
        }
      }, 100)

      logger.debug('[ServiceInitializer] Services pre-warmed')
    } catch (error) {
      logger.warn('[ServiceInitializer] Pre-warming failed (non-critical):', String(error))
      // Don't throw here - pre-warming is optional
    }
  }

  /**
   * Check if services are initialized
   */
  static isServicesInitialized(): boolean {
    return ServiceInitializer.isInitialized
  }

  /**
   * Check if services are currently being initialized
   */
  static isServicesInitializing(): boolean {
    return ServiceInitializer.isInitializing
  }

  /**
   * Reset initialization state (primarily for testing)
   */
  static reset(): void {
    ServiceInitializer.instance = null
    ServiceInitializer.initializationPromise = null
    ServiceInitializer.isInitialized = false
    ServiceInitializer.isInitializing = false
    
    // Also reset the UseCaseFactory
    UseCaseFactory.reset()
  }

  /**
   * Warm up specific services on demand
   */
  static async warmUpService(serviceName: 'schedule' | 'operator' | 'machine'): Promise<void> {
    if (!ServiceInitializer.isInitialized) {
      logger.warn('[ServiceInitializer] Cannot warm up service - services not initialized')
      return
    }

    try {
      const factory = UseCaseFactory.getInstance()
      
      switch (serviceName) {
        case 'schedule':
          await factory.getScheduleUseCases()
          break
        case 'operator':
          await factory.getOperatorUseCases()
          break
        case 'machine':
          await factory.getMachineUseCases()
          break
      }
      
      logger.debug(`[ServiceInitializer] Warmed up ${serviceName} service`)
    } catch (error) {
      logger.warn(`[ServiceInitializer] Failed to warm up ${serviceName} service:`, String(error))
    }
  }
}

export { ServiceInitializer }

/**
 * Convenience function for initializing services
 */
export const initializeServices = ServiceInitializer.initializeServices.bind(ServiceInitializer)

/**
 * Convenience function for checking initialization status
 */
export const isServicesInitialized = ServiceInitializer.isServicesInitialized.bind(ServiceInitializer)

/**
 * Convenience function for warming up specific services
 */
export const warmUpService = ServiceInitializer.warmUpService.bind(ServiceInitializer)