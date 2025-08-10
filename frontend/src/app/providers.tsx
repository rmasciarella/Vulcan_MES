'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createQueryClient } from '@/core/services/query-config-service'
import dynamic from 'next/dynamic'
const ReactQueryDevtools = process.env.NODE_ENV !== 'production'
  ? dynamic(() => import('@tanstack/react-query-devtools').then(m => ({ default: m.ReactQueryDevtools } as any)), {
      ssr: false,
      loading: () => null,
    })
  : (() => null) as any
import { ErrorBoundary } from '@/shared/components/error-boundary'
import { logger } from '@/shared/lib/logger'
import { useEffect } from 'react'
// TODO: Job event handlers moved to features/scheduling/api - import from there when implemented
// import { initializeJobEventHandlers, cleanupJobEventHandlers } from '@/core/use-cases/job-event-handlers'
import { initializeServices } from '@/core/initialization/service-initializer'

function makeQueryClient() {
  return createQueryClient()
}

let browserQueryClient: QueryClient | undefined = undefined

function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always make a new query client
    return makeQueryClient()
  } else {
    // Browser: make a new query client if we don't already have one
    // This is very important so we don't re-make a new client if React
    // suspends during the initial render. This may not be needed if we
    // have a suspense boundary BELOW the creation of the query client
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}

export function Providers({ children }: { children: React.ReactNode }) {
  // NOTE: Avoid useState when initializing the query client if you don't
  //       have a suspense boundary between this and the code that may
  //       suspend because React will throw away the client on the initial
  //       render if it suspends and there is no boundary
  const queryClient = getQueryClient()

  // Initialize core services and job event handlers
  // Optimized initialization with proper server/client boundaries
  useEffect(() => {
    let subscriptionIds: string[] = []
    let servicesInitialized = false

    const performInitialization = async () => {
      try {
        // Initialize core services (UseCaseFactory, etc.) with pre-warming
        await initializeServices({
          preWarm: true // Pre-warm commonly used services for better performance
        })
        servicesInitialized = true
        
        // TODO: Initialize job event handlers after core services are ready
        // const eventHandlerResult = initializeJobEventHandlers(queryClient)
        // subscriptionIds = eventHandlerResult.subscriptionIds
        
        logger.debug('[Providers] All services initialized successfully')
      } catch (error) {
        logger.error('[Providers] Failed to initialize services:', error as Error)
        servicesInitialized = false
      }
    }

    // Start initialization immediately (idempotent)
    performInitialization()
    
    // Return cleanup function
    return () => {
      if (servicesInitialized && subscriptionIds.length > 0) {
        // TODO: Cleanup job event handlers
        // cleanupJobEventHandlers(subscriptionIds)
        logger.debug('[Providers] Services cleanup completed')
      }
    }
  }, [queryClient])

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {children}
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
