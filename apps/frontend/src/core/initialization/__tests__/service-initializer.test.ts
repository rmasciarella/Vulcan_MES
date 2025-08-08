/**
 * Tests for ServiceInitializer idempotency and performance optimizations
 */
import { ServiceInitializer } from '../service-initializer'
import { UseCaseFactory } from '@/core/use-cases/use-case-factory'

// Mock the dependencies
jest.mock('@/infrastructure/supabase/browser-singleton')
jest.mock('@/shared/lib/logger')

describe('ServiceInitializer', () => {
  beforeEach(() => {
    // Reset state before each test
    ServiceInitializer.reset()
    jest.clearAllMocks()
  })

  afterEach(() => {
    ServiceInitializer.reset()
  })

  describe('initializeServices', () => {
    it('should initialize services only once when called multiple times', async () => {
      // First call should initialize
      await ServiceInitializer.initializeServices()
      expect(ServiceInitializer.isServicesInitialized()).toBe(true)
      
      // Subsequent calls should be no-op
      const secondCall = ServiceInitializer.initializeServices()
      const thirdCall = ServiceInitializer.initializeServices()
      
      await Promise.all([secondCall, thirdCall])
      
      // Should still be initialized
      expect(ServiceInitializer.isServicesInitialized()).toBe(true)
      
      // UseCaseFactory should only be initialized once
      expect(UseCaseFactory.isFactoryInitialized()).toBe(true)
    })

    it('should handle concurrent initialization calls', async () => {
      // Start multiple initialization calls simultaneously
      const initPromises = [
        ServiceInitializer.initializeServices(),
        ServiceInitializer.initializeServices(),
        ServiceInitializer.initializeServices()
      ]
      
      await Promise.all(initPromises)
      
      expect(ServiceInitializer.isServicesInitialized()).toBe(true)
      expect(ServiceInitializer.isServicesInitializing()).toBe(false)
    })

    it('should properly track initialization state', async () => {
      expect(ServiceInitializer.isServicesInitialized()).toBe(false)
      expect(ServiceInitializer.isServicesInitializing()).toBe(false)
      
      const initPromise = ServiceInitializer.initializeServices()
      
      // Should be initializing during the process
      expect(ServiceInitializer.isServicesInitializing()).toBe(true)
      expect(ServiceInitializer.isServicesInitialized()).toBe(false)
      
      await initPromise
      
      // Should be initialized after completion
      expect(ServiceInitializer.isServicesInitialized()).toBe(true)
      expect(ServiceInitializer.isServicesInitializing()).toBe(false)
    })

    it('should reset state properly', () => {
      ServiceInitializer.initializeServices()
      
      ServiceInitializer.reset()
      
      expect(ServiceInitializer.isServicesInitialized()).toBe(false)
      expect(ServiceInitializer.isServicesInitializing()).toBe(false)
      expect(UseCaseFactory.isFactoryInitialized()).toBe(false)
    })
  })

  describe('warmUpService', () => {
    beforeEach(async () => {
      await ServiceInitializer.initializeServices()
    })

    it('should warm up specific services', async () => {
      await expect(ServiceInitializer.warmUpService('schedule')).resolves.toBeUndefined()
      await expect(ServiceInitializer.warmUpService('operator')).resolves.toBeUndefined()
      await expect(ServiceInitializer.warmUpService('machine')).resolves.toBeUndefined()
    })

    it('should handle warming up services when not initialized', async () => {
      ServiceInitializer.reset()
      
      // Should not throw, just log warning
      await expect(ServiceInitializer.warmUpService('schedule')).resolves.toBeUndefined()
    })
  })
})