import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import { SupabaseScheduleRepository } from '@/infrastructure/supabase/repositories/supabase-schedule-repository'
import { ScheduleUseCasesImpl, type ScheduleUseCases } from './schedule-use-cases'
import { OperatorUseCases } from './operator-use-cases'
import { MachineUseCases } from './machine-use-cases'
import { JobUseCases } from './job-use-cases'
import { TaskUseCases } from './task-use-cases'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { Database } from '../../../types/supabase'

/**
 * Factory for creating use cases with dependency injection
 * Provides a singleton pattern to ensure consistent instances across the application
 */
export class UseCaseFactory {
  private static instance: UseCaseFactory | null = null
  private static isInitialized = false
  private static isInitializing = false
  private static initPromise: Promise<void> | null = null
  
  private scheduleUseCases: ScheduleUseCases | null = null
  private scheduleRepository: SupabaseScheduleRepository | null = null
  private operatorUseCases: OperatorUseCases | null = null
  private machineUseCases: MachineUseCases | null = null
  private jobUseCases: JobUseCases | null = null
  private taskUseCases: TaskUseCases | null = null
  private supabaseClient: SupabaseClient<Database> | null = null

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
    
    // Pre-warm critical dependencies that are commonly used
    // This prevents lazy loading delays during user interactions
    try {
      await instance.getScheduleRepository()
      console.debug('[UseCaseFactory] Pre-warmed schedule repository')
    } catch (error) {
      console.warn('[UseCaseFactory] Failed to pre-warm dependencies:', error)
      // Don't throw here - allow lazy loading to handle individual failures
    }
  }

  /**
   * Check if the factory has been initialized
   */
  static isFactoryInitialized(): boolean {
    return UseCaseFactory.isInitialized
  }

  /**
   * Get schedule use cases with lazy initialization
   */
  async getScheduleUseCases(): Promise<ScheduleUseCases> {
    if (!this.scheduleUseCases) {
      const repository = await this.getScheduleRepository()
      this.scheduleUseCases = new ScheduleUseCasesImpl(repository)
    }
    return this.scheduleUseCases
  }

  /**
   * Get operator use cases with lazy initialization
   */
  async getOperatorUseCases(): Promise<OperatorUseCases> {
    if (!this.operatorUseCases) {
      const supabase = this.supabaseClient || getSupabaseBrowserClient()
      this.operatorUseCases = new OperatorUseCases(supabase)
    }
    return this.operatorUseCases
  }

  /**
   * Get machine use cases with lazy initialization
   */
  async getMachineUseCases(): Promise<MachineUseCases> {
    if (!this.machineUseCases) {
      const supabase = this.supabaseClient || getSupabaseBrowserClient()
      this.machineUseCases = new MachineUseCases(supabase)
    }
    return this.machineUseCases
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
   * Get schedule repository with lazy initialization
   */
  private async getScheduleRepository(): Promise<SupabaseScheduleRepository> {
    if (!this.scheduleRepository) {
      const supabase = this.supabaseClient || getSupabaseBrowserClient()
      this.scheduleRepository = new SupabaseScheduleRepository(supabase)
    }
    return this.scheduleRepository
  }

  /**
   * Reset the factory instance (useful for testing)
   */
  static reset(): void {
    UseCaseFactory.instance = null
    UseCaseFactory.isInitialized = false
    UseCaseFactory.isInitializing = false
    UseCaseFactory.initPromise = null
  }

  /**
   * Clear cached instances to force recreation
   */
  clearCache(): void {
    this.scheduleUseCases = null
    this.scheduleRepository = null
    this.operatorUseCases = null
    this.machineUseCases = null
    this.jobUseCases = null
    this.taskUseCases = null
    this.supabaseClient = null
  }
}