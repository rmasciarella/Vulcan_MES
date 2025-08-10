import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import { machinesAPI, operatorsAPI } from './index'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '@/types/supabase'

/**
 * Resource use cases container for machines and operators
 */
export interface ResourceUseCases {
  machines: typeof machinesAPI
  operators: typeof operatorsAPI
}

/**
 * Factory for creating resource-specific use cases with dependency injection
 * Provides a singleton pattern to ensure consistent instances across the resource feature
 */
export class ResourceUseCaseFactory {
  private static instance: ResourceUseCaseFactory | null = null
  private static isInitialized = false
  private static isInitializing = false
  private static initPromise: Promise<void> | null = null
  
  private resourceUseCases: ResourceUseCases | null = null
  private supabaseClient: SupabaseClient<Database> | null = null

  private constructor() {
    // Private constructor to enforce singleton pattern
  }

  /**
   * Get the singleton instance of ResourceUseCaseFactory
   */
  static getInstance(): ResourceUseCaseFactory {
    if (!ResourceUseCaseFactory.instance) {
      ResourceUseCaseFactory.instance = new ResourceUseCaseFactory()
    }
    return ResourceUseCaseFactory.instance
  }

  /**
   * Initialize the factory with Supabase client (idempotent)
   * This method is safe to call multiple times and will only initialize once
   */
  static async initialize(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    // Return immediately if already initialized
    if (ResourceUseCaseFactory.isInitialized) {
      return
    }

    // If currently initializing, wait for the existing initialization to complete
    if (ResourceUseCaseFactory.isInitializing && ResourceUseCaseFactory.initPromise) {
      await ResourceUseCaseFactory.initPromise
      return
    }

    // Mark as initializing and create initialization promise
    ResourceUseCaseFactory.isInitializing = true
    ResourceUseCaseFactory.initPromise = ResourceUseCaseFactory._performInitialization(supabaseClient)

    try {
      await ResourceUseCaseFactory.initPromise
      ResourceUseCaseFactory.isInitialized = true
    } catch (error) {
      // Reset state on initialization failure
      ResourceUseCaseFactory.isInitializing = false
      ResourceUseCaseFactory.initPromise = null
      throw error
    } finally {
      ResourceUseCaseFactory.isInitializing = false
    }
  }

  /**
   * Internal initialization method
   */
  private static async _performInitialization(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    const instance = ResourceUseCaseFactory.getInstance()
    
    // Use provided client or get the browser singleton
    instance.supabaseClient = supabaseClient || getSupabaseBrowserClient()
    
    // Pre-warm resource use cases
    try {
      await instance.getResourceUseCases()
      console.debug('[ResourceUseCaseFactory] Pre-warmed resource use cases')
    } catch (error) {
      console.warn('[ResourceUseCaseFactory] Failed to pre-warm dependencies:', error)
      // Don't throw here - allow lazy loading to handle individual failures
    }
  }

  /**
   * Check if the factory has been initialized
   */
  static isFactoryInitialized(): boolean {
    return ResourceUseCaseFactory.isInitialized
  }

  /**
   * Get resource use cases with lazy initialization
   */
  async getResourceUseCases(): Promise<ResourceUseCases> {
    if (!this.resourceUseCases) {
      // API instances are already singletons with built-in client management
      this.resourceUseCases = {
        machines: machinesAPI,
        operators: operatorsAPI,
      }
    }
    return this.resourceUseCases
  }

  /**
   * Get machine use cases specifically
   */
  async getMachineUseCases() {
    const resources = await this.getResourceUseCases()
    return resources.machines
  }

  /**
   * Get operator use cases specifically  
   */
  async getOperatorUseCases() {
    const resources = await this.getResourceUseCases()
    return resources.operators
  }

  /**
   * Reset the factory instance (useful for testing)
   */
  static reset(): void {
    ResourceUseCaseFactory.instance = null
    ResourceUseCaseFactory.isInitialized = false
    ResourceUseCaseFactory.isInitializing = false
    ResourceUseCaseFactory.initPromise = null
  }

  /**
   * Clear cached instances to force recreation
   */
  clearCache(): void {
    this.resourceUseCases = null
    this.supabaseClient = null
  }
}