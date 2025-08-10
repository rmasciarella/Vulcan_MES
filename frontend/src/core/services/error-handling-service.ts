import { getNotificationService } from './notification-service'
import { 
  ManufacturingError, 
  SchedulingError, 
  ResourceConflictError, 
  DatabaseConnectionError 
} from '@/infrastructure/supabase/errors'
// Simple HttpError class (replaced deprecated http-client import)
class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'HttpError'
  }
}

/**
 * Unified error handling service that translates all error types
 * to consistent user notifications and provides error recovery strategies
 */
export interface ErrorHandlingService {
  handleError: (error: unknown, context?: ErrorContext) => void
  translateError: (error: unknown) => ErrorTranslation
  shouldRetry: (error: unknown) => boolean
  getRetryDelay: (error: unknown, attempt: number) => number
}

export interface ErrorContext {
  operation?: string
  component?: string
  metadata?: Record<string, unknown>
}

export interface ErrorTranslation {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  retryable: boolean
  severity: 'low' | 'medium' | 'high' | 'critical'
}

/**
 * Default implementation of unified error handling
 */
class DefaultErrorHandlingService implements ErrorHandlingService {
  private notificationService = getNotificationService()

  handleError(error: unknown, context?: ErrorContext): void {
    const translation = this.translateError(error)
    
    // Log error with context for monitoring
    this.logError(error, context, translation)
    
    // Show user notification
    this.notificationService.addNotification({
      type: translation.type,
      title: translation.title,
      message: translation.message,
      autoClose: translation.severity !== 'critical'
    })
  }

  translateError(error: unknown): ErrorTranslation {
    // Manufacturing domain errors
    if (error instanceof ManufacturingError) {
      return this.translateManufacturingError(error)
    }

    // HTTP client errors
    if (error instanceof HttpError) {
      return this.translateHttpError(error)
    }

    // TanStack Query errors
    if (this.isTanStackQueryError(error)) {
      return this.translateQueryError(error)
    }

    // Generic error fallback
    return this.translateGenericError(error)
  }

  shouldRetry(error: unknown): boolean {
    if (error instanceof DatabaseConnectionError) return true
    if (error instanceof HttpError && error.status >= 500) return true
    if (this.isTanStackQueryError(error)) {
      const queryError = error as any
      return queryError.status >= 500 || queryError.message?.includes('network')
    }
    
    const errorMessage = this.getErrorMessage(error).toLowerCase()
    return errorMessage.includes('network') || 
           errorMessage.includes('timeout') || 
           errorMessage.includes('connection')
  }

  getRetryDelay(error: unknown, attempt: number): number {
    const baseDelay = 1000 // 1 second
    const maxDelay = 10000 // 10 seconds
    
    // Exponential backoff with jitter
    const exponentialDelay = baseDelay * Math.pow(2, attempt - 1)
    const jitter = Math.random() * 0.1 * exponentialDelay
    
    return Math.min(exponentialDelay + jitter, maxDelay)
  }

  private translateManufacturingError(error: ManufacturingError): ErrorTranslation {
    const baseTranslation = {
      type: 'error' as const,
      retryable: false
    }

    if (error instanceof SchedulingError) {
      return {
        ...baseTranslation,
        title: 'Scheduling Error',
        message: `Production scheduling failed: ${error.message}`,
        severity: 'high'
      }
    }

    if (error instanceof ResourceConflictError) {
      return {
        ...baseTranslation,
        title: 'Resource Conflict',
        message: `Resource allocation conflict: ${error.message}`,
        severity: 'high'
      }
    }

    if (error instanceof DatabaseConnectionError) {
      return {
        ...baseTranslation,
        title: 'System Connectivity',
        message: 'Manufacturing system temporarily unavailable. Retrying automatically.',
        severity: 'critical',
        retryable: true
      }
    }

    // Generic manufacturing error
    return {
      ...baseTranslation,
      title: 'Manufacturing System Error',
      message: error.message || 'An error occurred in the manufacturing system',
      severity: 'medium'
    }
  }

  private translateHttpError(error: HttpError): ErrorTranslation {
    const baseTranslation = {
      type: 'error' as const,
      retryable: false
    }

    if (error.status >= 500) {
      return {
        ...baseTranslation,
        title: 'Server Error',
        message: 'Server is temporarily unavailable. Please try again.',
        severity: 'high',
        retryable: true
      }
    }

    if (error.status === 401) {
      return {
        ...baseTranslation,
        title: 'Authentication Required',
        message: 'Please log in to continue.',
        severity: 'medium'
      }
    }

    if (error.status === 403) {
      return {
        ...baseTranslation,
        title: 'Access Denied',
        message: 'You do not have permission to perform this action.',
        severity: 'medium'
      }
    }

    if (error.status === 404) {
      return {
        ...baseTranslation,
        title: 'Not Found',
        message: 'The requested resource could not be found.',
        severity: 'low'
      }
    }

    if (error.status === 408 || error.status === 0) {
      return {
        ...baseTranslation,
        title: 'Request Timeout',
        message: 'Request timed out. Please check your connection.',
        severity: 'medium',
        retryable: true
      }
    }

    return {
      ...baseTranslation,
      title: 'Request Failed',
      message: error.message || `Request failed with status ${error.status}`,
      severity: 'medium'
    }
  }

  private translateQueryError(error: any): ErrorTranslation {
    const baseTranslation = {
      type: 'error' as const,
      retryable: false
    }

    // Check for network errors
    if (error.message?.includes('fetch') || error.message?.includes('network')) {
      return {
        ...baseTranslation,
        title: 'Network Error',
        message: 'Unable to connect to the server. Please check your connection.',
        severity: 'high',
        retryable: true
      }
    }

    // Check for timeout errors
    if (error.message?.includes('timeout')) {
      return {
        ...baseTranslation,
        title: 'Request Timeout',
        message: 'Request timed out. The server may be busy.',
        severity: 'medium',
        retryable: true
      }
    }

    return {
      ...baseTranslation,
      title: 'Data Loading Error',
      message: 'Failed to load data. Please try again.',
      severity: 'medium',
      retryable: true
    }
  }

  private translateGenericError(error: unknown): ErrorTranslation {
    const message = this.getErrorMessage(error)
    
    return {
      type: 'error',
      title: 'Unexpected Error',
      message: message || 'An unexpected error occurred',
      severity: 'medium',
      retryable: false
    }
  }

  private isTanStackQueryError(error: unknown): boolean {
    return Boolean(error && typeof error === 'object' && 'status' in error)
  }

  private getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message
    if (typeof error === 'string') return error
    if (error && typeof error === 'object' && 'message' in error) {
      return String(error.message)
    }
    return String(error)
  }

  private logError(error: unknown, context?: ErrorContext, translation?: ErrorTranslation): void {
    const logData = {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
      context,
      translation,
      timestamp: new Date().toISOString(),
      url: typeof window !== 'undefined' ? window.location.href : undefined
    }

    if (process.env.NODE_ENV === 'production') {
      // In production, send to monitoring service
      console.error('[ErrorHandlingService]', logData)
      // TODO: Send to monitoring service (Sentry, DataDog, etc.)
    } else {
      console.error('[ErrorHandlingService]', error, logData)
    }
  }
}

// Singleton instance
let errorHandlingService: ErrorHandlingService

export function getErrorHandlingService(): ErrorHandlingService {
  if (!errorHandlingService) {
    errorHandlingService = new DefaultErrorHandlingService()
  }
  return errorHandlingService
}

// For testing: allow setting a custom error handling service
export function setErrorHandlingService(service: ErrorHandlingService) {
  errorHandlingService = service
}

// Convenience hook for React components
export function useErrorHandling() {
  const service = getErrorHandlingService()
  
  return {
    handleError: service.handleError,
    translateError: service.translateError,
    shouldRetry: service.shouldRetry,
    getRetryDelay: service.getRetryDelay
  }
}