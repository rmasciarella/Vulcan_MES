import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import { JobUseCases } from './job-use-cases'
import { TaskUseCases } from './task-use-cases'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '../../../types/supabase'

/**
 * Factory for creating scheduling-specific use cases with dependency injection
 * Provides a singleton pattern to ensure consistent instances across the scheduling feature
 */
export class SchedulingUseCaseFactory {
  private static instance: SchedulingUseCaseFactory | null = null
  private static isInitialized = false
  private static isInitializing = false
  private static initPromise: Promise<void> | null = null
  
  private jobUseCases: JobUseCases | null = null
  private taskUseCases: TaskUseCases | null = null
  private supabaseClient: SupabaseClient<Database> | null = null

  private constructor() {
    // Private constructor to enforce singleton pattern
  }

  /**
   * Get the singleton instance of SchedulingUseCaseFactory
   */
  static getInstance(): SchedulingUseCaseFactory {
    if (!SchedulingUseCaseFactory.instance) {
      SchedulingUseCaseFactory.instance = new SchedulingUseCaseFactory()
    }
    return SchedulingUseCaseFactory.instance
  }

  /**
   * Initialize the factory with Supabase client (idempotent)
   * This method is safe to call multiple times and will only initialize once
   */
  static async initialize(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    // Return immediately if already initialized
    if (SchedulingUseCaseFactory.isInitialized) {
      return
    }

    // If currently initializing, wait for the existing initialization to complete
    if (SchedulingUseCaseFactory.isInitializing && SchedulingUseCaseFactory.initPromise) {
      await SchedulingUseCaseFactory.initPromise
      return
    }

    // Mark as initializing and create initialization promise
    SchedulingUseCaseFactory.isInitializing = true
    SchedulingUseCaseFactory.initPromise = SchedulingUseCaseFactory._performInitialization(supabaseClient)

    try {
      await SchedulingUseCaseFactory.initPromise
      SchedulingUseCaseFactory.isInitialized = true
    } catch (error) {
      // Reset state on initialization failure
      SchedulingUseCaseFactory.isInitializing = false
      SchedulingUseCaseFactory.initPromise = null
      throw error
    } finally {
      SchedulingUseCaseFactory.isInitializing = false
    }
  }

  /**
   * Internal initialization method
   */
  private static async _performInitialization(supabaseClient?: SupabaseClient<Database>): Promise<void> {
    const instance = SchedulingUseCaseFactory.getInstance()
    
    // Use provided client or get the browser singleton
    instance.supabaseClient = supabaseClient || getSupabaseBrowserClient()
    
    // Pre-warm critical dependencies that are commonly used
    // This prevents lazy loading delays during user interactions
    try {
      await instance.getJobUseCases()
      console.debug('[SchedulingUseCaseFactory] Pre-warmed job use cases')
    } catch (error) {
      console.warn('[SchedulingUseCaseFactory] Failed to pre-warm dependencies:', error)
      // Don't throw here - allow lazy loading to handle individual failures
    }
  }

  /**
   * Check if the factory has been initialized
   */
  static isFactoryInitialized(): boolean {
    return SchedulingUseCaseFactory.isInitialized
  }

  /**
   * Get job use cases with lazy initialization
   */
  async getJobUseCases(): Promise<JobUseCases> {
    if (!this.jobUseCases) {
      const supabase = this.supabaseClient || getSupabaseBrowserClient()
      this.jobUseCases = new JobUseCases(supabase)
    }
    return this.jobUseCases
  }

  /**
   * Get task use cases with lazy initialization
   */
  async getTaskUseCases(): Promise<TaskUseCases> {
    if (!this.taskUseCases) {
      const supabase = this.supabaseClient || getSupabaseBrowserClient()
      this.taskUseCases = new TaskUseCases(supabase)
    }
    return this.taskUseCases
  }

  /**
   * Reset the factory instance (useful for testing)
   */
  static reset(): void {
    SchedulingUseCaseFactory.instance = null
    SchedulingUseCaseFactory.isInitialized = false
    SchedulingUseCaseFactory.isInitializing = false
    SchedulingUseCaseFactory.initPromise = null
  }

  /**
   * Clear cached instances to force recreation
   */
  clearCache(): void {
    this.jobUseCases = null
    this.taskUseCases = null
    this.supabaseClient = null
  }
}