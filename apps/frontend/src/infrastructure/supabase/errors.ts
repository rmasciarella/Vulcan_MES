/**
 * Manufacturing-specific error types and utilities for Supabase operations
 * Critical for production scheduling system reliability
 */

export class ManufacturingError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly context?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ManufacturingError'
  }
}

export class SchedulingError extends ManufacturingError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, 'SCHEDULING_ERROR', context)
    this.name = 'SchedulingError'
  }
}

export class ResourceConflictError extends ManufacturingError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, 'RESOURCE_CONFLICT', context)
    this.name = 'ResourceConflictError'
  }
}

export class DatabaseConnectionError extends ManufacturingError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, 'DATABASE_CONNECTION', context)
    this.name = 'DatabaseConnectionError'
  }
}

/**
 * Handle Supabase errors and convert to manufacturing-specific errors
 */
export function handleSupabaseError(error: unknown, operation: string): ManufacturingError {
  const baseMessage = `${operation} failed`

  // Type guard for error object
  const errorObj = error && typeof error === 'object' ? (error as Record<string, unknown>) : {}
  const errorCode = typeof errorObj.code === 'string' ? errorObj.code : undefined
  const errorMessage = typeof errorObj.message === 'string' ? errorObj.message : String(error)

  // Common Supabase error codes
  switch (errorCode) {
    case 'PGRST116':
      return new ManufacturingError(`${baseMessage}: Resource not found`, 'NOT_FOUND', {
        operation,
        originalError: errorMessage,
      })

    case 'PGRST301':
      return new ResourceConflictError(
        `${baseMessage}: Resource conflict - another operation may be in progress`,
        { operation, originalError: errorMessage },
      )

    case '23505': // Unique constraint violation
      return new ResourceConflictError(`${baseMessage}: Duplicate resource allocation detected`, {
        operation,
        originalError: errorMessage,
      })

    case '23503': // Foreign key constraint violation
      return new ManufacturingError(
        `${baseMessage}: Referenced resource does not exist`,
        'INVALID_REFERENCE',
        { operation, originalError: errorMessage },
      )

    case 'PGRST000':
    case 'PGRST001':
      return new DatabaseConnectionError(
        `${baseMessage}: Database connection issue - this may affect production scheduling`,
        { operation, originalError: errorMessage },
      )

    default:
      // Check for network/connection errors
      if (errorMessage.includes('fetch') || errorMessage.includes('network')) {
        return new DatabaseConnectionError(`${baseMessage}: Network connectivity issue`, {
          operation,
          originalError: errorMessage,
        })
      }

      return new ManufacturingError(
        `${baseMessage}: ${errorMessage || 'Unknown error'}`,
        'UNKNOWN_ERROR',
        { operation, originalError: error },
      )
  }
}

/**
 * Retry configuration for manufacturing operations
 */
export const manufacturingRetryConfig = {
  // Critical operations (scheduling, resource allocation)
  critical: {
    maxAttempts: 5,
    baseDelay: 1000, // 1 second
    maxDelay: 10000, // 10 seconds
    exponentialBase: 2,
  },

  // Standard operations (data fetching, updates)
  standard: {
    maxAttempts: 3,
    baseDelay: 500, // 0.5 seconds
    maxDelay: 5000, // 5 seconds
    exponentialBase: 2,
  },

  // Low priority operations (analytics, reporting)
  lowPriority: {
    maxAttempts: 2,
    baseDelay: 2000, // 2 seconds
    maxDelay: 8000, // 8 seconds
    exponentialBase: 1.5,
  },
}

/**
 * Retry function with exponential backoff for manufacturing operations
 */
export async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  config: typeof manufacturingRetryConfig.standard,
  operationName: string,
): Promise<T> {
  let lastError: unknown

  for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
    try {
      return await operation()
    } catch (error) {
      lastError = error

      // Don't retry client errors (4xx)
      if (error instanceof ManufacturingError && error.code === 'NOT_FOUND') {
        throw error
      }

      // Don't retry on final attempt
      if (attempt === config.maxAttempts) {
        break
      }

      // Calculate delay with exponential backoff
      const delay = Math.min(
        config.baseDelay * Math.pow(config.exponentialBase, attempt - 1),
        config.maxDelay,
      )

      console.warn(
        `[Manufacturing] ${operationName} attempt ${attempt} failed, retrying in ${delay}ms:`,
        error instanceof Error ? error.message : String(error),
      )

      await new Promise((resolve) => setTimeout(resolve, delay))
    }
  }

  // All attempts failed
  throw handleSupabaseError(lastError, operationName)
}

/**
 * Check if an error is recoverable (should be retried)
 */
export function isRecoverableError(error: unknown): boolean {
  if (error instanceof DatabaseConnectionError) {
    return true
  }

  if (error instanceof ManufacturingError) {
    return ['DATABASE_CONNECTION', 'UNKNOWN_ERROR'].includes(error.code)
  }

  // Network errors are generally recoverable
  const errorMessage =
    error && typeof error === 'object' && 'message' in error && typeof error.message === 'string'
      ? error.message
      : String(error)
  if (errorMessage.includes('fetch') || errorMessage.includes('network')) {
    return true
  }

  return false
}

/**
 * Log manufacturing-specific errors with appropriate context
 */
export function logManufacturingError(
  error: ManufacturingError,
  additionalContext?: Record<string, unknown>,
) {
  const logContext = {
    errorCode: error.code,
    errorMessage: error.message,
    context: error.context,
    additionalContext,
    timestamp: new Date().toISOString(),
    severity: getErrorSeverity(error),
  }

  // In production, this would integrate with monitoring service
  if (process.env.NODE_ENV === 'production') {
    console.error('[Manufacturing Error]', logContext)
    // TODO: Send to monitoring service (Sentry, DataDog, etc.)
  } else {
    console.error('[Manufacturing Error]', error.message, logContext)
  }
}

/**
 * Determine error severity for manufacturing context
 */
function getErrorSeverity(error: ManufacturingError): 'low' | 'medium' | 'high' | 'critical' {
  switch (error.code) {
    case 'DATABASE_CONNECTION':
      return 'critical' // Database issues affect entire production
    case 'RESOURCE_CONFLICT':
      return 'high' // Resource conflicts can block scheduling
    case 'SCHEDULING_ERROR':
      return 'high' // Scheduling failures affect production planning
    case 'NOT_FOUND':
      return 'medium' // Missing resources may indicate data issues
    default:
      return 'low'
  }
}
