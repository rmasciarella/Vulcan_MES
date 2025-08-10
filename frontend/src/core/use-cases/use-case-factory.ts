import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import { SchedulingUseCaseFactory } from '@/features/scheduling/api/use-case-factory'
import { ResourceUseCaseFactory } from '@/features/resources/api/use-case-factory'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '@/types/supabase'

/**
 * Main use case factory that coordinates all feature-specific factories
 * Provides a unified interface for accessing use cases across the application
 */
export class UseCaseFactory {
  private static instance: UseCaseFactory | null = null
  private static isInitialized = false
  private static isInitializing = false
  private static initPromise: Promise<void> | null = null

  private supabaseClient: SupabaseClient<Database> | undefined = undefined
  private schedulingFactory: SchedulingUseCaseFactory | null = null
  private resourceFactory: ResourceUseCaseFactory | null = null

  private constructor() {
    // Private constructor to enforce singleton pattern
  }

  /**
   * Get the singleton instance of UseCaseFactory
   */
  static getInstance(): UseCaseFactory {
    if (!UseCaseFactory.instance) {
      UseCaseFactory.instance = new UseCaseFactory()
    }
    return UseCaseFactory.instance
  }

  /**
   * Initialize the factory with Supabase client (idempotent)
   * This method is safe to call multiple times and will only initialize once
   */
  static async initialize(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    // Return immediately if already initialized
    if (UseCaseFactory.isInitialized) {
      return
    }

    // If currently initializing, wait for the existing initialization to complete
    if (UseCaseFactory.isInitializing && UseCaseFactory.initPromise) {
      await UseCaseFactory.initPromise
      return
    }

    // Mark as initializing and create initialization promise
    UseCaseFactory.isInitializing = true
    UseCaseFactory.initPromise = UseCaseFactory._performInitialization(supabaseClient)

    try {
      await UseCaseFactory.initPromise
      UseCaseFactory.isInitialized = true
    } catch (error) {
      // Reset state on initialization failure
      UseCaseFactory.isInitializing = false
      UseCaseFactory.initPromise = null
      throw error
    } finally {
      UseCaseFactory.isInitializing = false
    }
  }

  /**
   * Internal initialization method
   */
  private static async _performInitialization(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    const instance = UseCaseFactory.getInstance()
    
    // Use provided client or get the browser singleton
    instance.supabaseClient = supabaseClient || getSupabaseBrowserClient()
    
    // Initialize feature-specific factories
    await Promise.all([
      SchedulingUseCaseFactory.initialize(instance.supabaseClient!),
      ResourceUseCaseFactory.initialize(instance.supabaseClient!),
    ])
    
    // Store factory instances
    instance.schedulingFactory = SchedulingUseCaseFactory.getInstance()
    instance.resourceFactory = ResourceUseCaseFactory.getInstance()

    console.debug('[UseCaseFactory] All feature factories initialized')
  }

  /**
   * Check if the factory has been initialized
   */
  static isFactoryInitialized(): boolean {
    return UseCaseFactory.isInitialized
  }

  /**
   * Get scheduling use cases
   */
  async getScheduleUseCases() {
    if (!this.schedulingFactory) {
      this.schedulingFactory = SchedulingUseCaseFactory.getInstance()
      await SchedulingUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.schedulingFactory.getJobUseCases()
  }

  /**
   * Get job use cases (alias for backward compatibility)
   */
  async getJobUseCases() {
    if (!this.schedulingFactory) {
      this.schedulingFactory = SchedulingUseCaseFactory.getInstance()
      await SchedulingUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.schedulingFactory.getJobUseCases()
  }

  /**
   * Get task use cases
   */
  async getTaskUseCases() {
    if (!this.schedulingFactory) {
      this.schedulingFactory = SchedulingUseCaseFactory.getInstance()
      await SchedulingUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.schedulingFactory.getTaskUseCases()
  }

  /**
   * Get machine use cases
   */
  async getMachineUseCases() {
    if (!this.resourceFactory) {
      this.resourceFactory = ResourceUseCaseFactory.getInstance()
      await ResourceUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.resourceFactory.getMachineUseCases()
  }

  /**
   * Get operator use cases
   */
  async getOperatorUseCases() {
    if (!this.resourceFactory) {
      this.resourceFactory = ResourceUseCaseFactory.getInstance()
      await ResourceUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.resourceFactory.getOperatorUseCases()
  }

  /**
   * Get all resource use cases
   */
  async getResourceUseCases() {
    if (!this.resourceFactory) {
      this.resourceFactory = ResourceUseCaseFactory.getInstance()
      await ResourceUseCaseFactory.initialize(this.supabaseClient || undefined)
    }
    return this.resourceFactory.getResourceUseCases()
  }

  /**
   * Reset the factory instance (useful for testing)
   */
  static reset(): void {
    // Reset all factory instances
    SchedulingUseCaseFactory.reset()
    ResourceUseCaseFactory.reset()
    
    // Reset main factory
    UseCaseFactory.instance = null
    UseCaseFactory.isInitialized = false
    UseCaseFactory.isInitializing = false
    UseCaseFactory.initPromise = null
  }

  /**
   * Clear cached instances to force recreation
   */
  clearCache(): void {
    this.schedulingFactory?.clearCache()
    this.resourceFactory?.clearCache()
    this.schedulingFactory = null
    this.resourceFactory = null
    this.supabaseClient = undefined
  }
}