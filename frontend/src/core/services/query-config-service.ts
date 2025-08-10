import { QueryClient, DefaultOptions } from '@tanstack/react-query'
import { getErrorHandlingService } from './error-handling-service'

/**
 * Unified query configuration service that provides consistent
 * TanStack Query settings across the entire application
 */

export interface QueryConfig {
  staleTime: number
  cacheTime: number
  refetchOnWindowFocus: boolean
  retry: boolean | number | ((failureCount: number, error: unknown) => boolean)
  retryDelay: (attemptIndex: number) => number
}

export const queryConfigurations = {
  // Real-time data (jobs status, machine state)
  realtime: {
    staleTime: 30 * 1000, // 30 seconds
    cacheTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: true,
    refetchInterval: 60 * 1000, // 1 minute
    retry: (failureCount: number, error: unknown) => {
      const errorService = getErrorHandlingService()
      return failureCount < 3 && errorService.shouldRetry(error)
    },
    retryDelay: (attemptIndex: number) => {
      const errorService = getErrorHandlingService()
      return errorService.getRetryDelay({}, attemptIndex)
    }
  } as QueryConfig & { refetchInterval: number },

  // Frequently changing data (schedules, task assignments)
  frequent: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: true,
    retry: (failureCount: number, error: unknown) => {
      const errorService = getErrorHandlingService()
      return failureCount < 3 && errorService.shouldRetry(error)
    },
    retryDelay: (attemptIndex: number) => {
      const errorService = getErrorHandlingService()
      return errorService.getRetryDelay({}, attemptIndex)
    }
  } as QueryConfig,

  // Standard data (jobs list, machine list)
  standard: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 30 * 60 * 1000, // 30 minutes
    refetchOnWindowFocus: false,
    retry: (failureCount: number, error: unknown) => {
      const errorService = getErrorHandlingService()
      return failureCount < 2 && errorService.shouldRetry(error)
    },
    retryDelay: (attemptIndex: number) => {
      const errorService = getErrorHandlingService()
      return errorService.getRetryDelay({}, attemptIndex)
    }
  } as QueryConfig,

  // Static/reference data (machine types, operators, departments)
  static: {
    staleTime: 30 * 60 * 1000, // 30 minutes
    cacheTime: 60 * 60 * 1000, // 1 hour
    refetchOnWindowFocus: false,
    retry: 1,
    retryDelay: () => 2000 // 2 seconds
  } as QueryConfig,

  // Analytics/reporting data
  analytics: {
    staleTime: 10 * 60 * 1000, // 10 minutes
    cacheTime: 60 * 60 * 1000, // 1 hour
    refetchOnWindowFocus: false,
    retry: 1,
    retryDelay: () => 5000 // 5 seconds
  } as QueryConfig,

  // Critical operations (scheduling, resource allocation)
  critical: {
    staleTime: 1000, // 1 second
    cacheTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: true,
    retry: (failureCount: number, error: unknown) => {
      const errorService = getErrorHandlingService()
      return failureCount < 5 && errorService.shouldRetry(error)
    },
    retryDelay: (attemptIndex: number) => {
      const errorService = getErrorHandlingService()
      return errorService.getRetryDelay({}, attemptIndex)
    }
  } as QueryConfig
}

/**
 * Create a standardized query client with unified error handling
 */
export function createQueryClient(): QueryClient {
  const errorHandlingService = getErrorHandlingService()

  const defaultOptions: DefaultOptions = {
    queries: {
      ...queryConfigurations.standard,
      // Global error handling for queries
      throwOnError: false, // Let components handle errors via error states
      // Global retry configuration with unified error handling
      retry: (failureCount: number, error: unknown) => {
        // Log error for monitoring
        errorHandlingService.handleError(error, {
          operation: 'Query execution',
          component: 'QueryClient',
          metadata: { failureCount, retry: true }
        })
        
        return failureCount < 2 && errorHandlingService.shouldRetry(error)
      },
      retryDelay: (attemptIndex: number) => {
        return errorHandlingService.getRetryDelay({}, attemptIndex)
      }
    },
    mutations: {
      // Global error handling for mutations
      throwOnError: false,
      retry: (failureCount: number, error: unknown) => {
        // Don't retry mutations by default (they often have side effects)
        return false
      },
      // Mutations get logged but don't auto-retry
      onError: (error: unknown) => {
        errorHandlingService.handleError(error, {
          operation: 'Mutation execution',
          component: 'QueryClient'
        })
      }
    }
  }

  const queryClient = new QueryClient({ defaultOptions })
  
  // Custom logging can be handled through global error handling
  // or by setting up custom mutations/queries with onError callbacks
  
  return queryClient
}

/**
 * Helper to get query options for specific data types
 */
export function getQueryConfig(type: keyof typeof queryConfigurations) {
  return queryConfigurations[type]
}

/**
 * Hook to get query configuration for use in components
 */
export function useQueryConfig(type: keyof typeof queryConfigurations) {
  return getQueryConfig(type)
}

/**
 * Utility to create query options with error handling
 */
export function createQueryOptions<T>(
  config: Partial<QueryConfig> & {
    queryKey: unknown[]
    queryFn: () => Promise<T>
    enabled?: boolean
    meta?: Record<string, unknown>
  }
) {
  const errorService = getErrorHandlingService()
  
  return {
    queryKey: config.queryKey,
    queryFn: config.queryFn,
    enabled: config.enabled,
    staleTime: config.staleTime || queryConfigurations.standard.staleTime,
    cacheTime: config.cacheTime || queryConfigurations.standard.cacheTime,
    refetchOnWindowFocus: config.refetchOnWindowFocus ?? queryConfigurations.standard.refetchOnWindowFocus,
    retry: config.retry || ((failureCount: number, error: unknown) => {
      return failureCount < 2 && errorService.shouldRetry(error)
    }),
    retryDelay: config.retryDelay || ((attemptIndex: number) => {
      return errorService.getRetryDelay({}, attemptIndex)
    }),
    meta: config.meta,
    onError: (error: unknown) => {
      errorService.handleError(error, {
        operation: 'Query failed',
        component: 'createQueryOptions',
        metadata: { queryKey: config.queryKey, ...config.meta }
      })
    }
  }
}

/**
 * Utility to create mutation options with error handling
 */
export function createMutationOptions<TData, TError, TVariables>(config: {
  mutationFn: (variables: TVariables) => Promise<TData>
  onSuccess?: (data: TData, variables: TVariables) => void
  onError?: (error: TError, variables: TVariables) => void
  onSettled?: (data: TData | undefined, error: TError | null, variables: TVariables) => void
  meta?: Record<string, unknown>
}) {
  const errorService = getErrorHandlingService()
  
  return {
    mutationFn: config.mutationFn,
    onSuccess: config.onSuccess,
    onError: (error: TError, variables: TVariables) => {
      // Call custom error handler first
      config.onError?.(error, variables)
      
      // Then handle with unified error service
      errorService.handleError(error, {
        operation: 'Mutation failed',
        component: 'createMutationOptions',
        metadata: { variables, ...config.meta }
      })
    },
    onSettled: config.onSettled,
    meta: config.meta
  }
}