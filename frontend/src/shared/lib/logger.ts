// Simple logging utility for manufacturing system
// In production, this should integrate with a proper logging service

type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'critical'

interface LogContext {
  userId?: string
  facilityId?: string
  jobId?: string
  machineId?: string
  operatorId?: string
  scheduleId?: string
  event?: string
  duration?: number
  operation?: string
  error?: string
  severity?: string
  changeType?: string
  [key: string]: string | number | boolean | undefined
}

type LogInput = LogContext | Error | undefined

class Logger {
  private isDevelopment = process.env.NODE_ENV === 'development'

  private normalizeContext(input: LogInput): LogContext | undefined {
    if (!input) return undefined
    if (input instanceof Error) {
      return { error: input.message, stack: (input as any).stack }
    }
    return input
  }

  private log(level: LogLevel, message: string, context?: LogInput) {
    const timestamp = new Date().toISOString()
    const normalized = this.normalizeContext(context)
    const logEntry = {
      timestamp,
      level,
      message,
      context: normalized,
      environment: process.env.NODE_ENV,
    }

    // In development, use console methods
    if (this.isDevelopment) {
      switch (level) {
        case 'debug':
          console.debug(`[${timestamp}] DEBUG:`, message, normalized)
          break
        case 'info':
          console.info(`[${timestamp}] INFO:`, message, normalized)
          break
        case 'warn':
          console.warn(`[${timestamp}] WARN:`, message, normalized)
          break
        case 'error':
        case 'critical':
          console.error(`[${timestamp}] ${level.toUpperCase()}:`, message, normalized)
          break
      }
    } else {
      // In production, send to logging service
      // TODO: Implement production logging (e.g., to Supabase logs table or external service)
      if (level === 'error' || level === 'critical') {
        console.error(JSON.stringify(logEntry))
      }
    }

    // For critical errors in manufacturing, could trigger alerts
    if (level === 'critical') {
      this.handleCriticalError(message, context)
    }
  }

  private handleCriticalError(_message: string, _context?: LogInput) {
    // In a real manufacturing system, this would:
    // - Send alerts to supervisors
    // - Possibly halt affected production lines
    // - Create incident tickets
    // For now, just ensure it's logged
    if (!this.isDevelopment) {
      // TODO: Implement critical error handling
    }
  }

  debug(message: string, context?: LogInput) {
    this.log('debug', message, context)
  }

  info(message: string, context?: LogInput) {
    this.log('info', message, context)
  }

  warn(message: string, context?: LogInput) {
    this.log('warn', message, context)
  }

  error(message: string, context?: LogInput) {
    this.log('error', message, context)
  }

  critical(message: string, context?: LogInput) {
    this.log('critical', message, context)
  }

  // Manufacturing-specific logging methods
  logJobStart(jobId: string, machineId: string, operatorId?: string) {
    this.info('Job started', {
      jobId,
      machineId,
      ...(operatorId !== undefined && { operatorId }),
      event: 'job_start',
    })
  }

  logJobComplete(jobId: string, machineId: string, duration: number) {
    this.info('Job completed', {
      jobId,
      machineId,
      duration,
      event: 'job_complete',
    })
  }

  logMachineError(machineId: string, error: string, severity: 'warning' | 'critical') {
    const logMethod = severity === 'critical' ? this.critical : this.warn
    logMethod.call(this, `Machine error: ${error}`, {
      machineId,
      event: 'machine_error',
      severity,
    })
  }

  logScheduleChange(scheduleId: string, changeType: string, userId: string) {
    this.info('Schedule modified', {
      scheduleId,
      changeType,
      userId,
      event: 'schedule_change',
    })
  }

  // Performance logging for manufacturing operations
  logPerformance(operation: string, duration: number, context?: LogContext) {
    const level = duration > 5000 ? 'warn' : 'info'
    this.log(level, `Performance: ${operation} took ${duration}ms`, {
      ...context,
      duration,
      operation,
      event: 'performance',
    })
  }
}

// Export singleton instance
export const logger = new Logger()

// Utility to measure and log performance
export function measurePerformance<T>(
  operation: string,
  fn: () => T | Promise<T>,
  context?: LogContext,
): T | Promise<T> {
  const start = performance.now()

  try {
    const result = fn()

    if (result instanceof Promise) {
      return result.finally(() => {
        const duration = performance.now() - start
        logger.logPerformance(operation, duration, context)
      })
    }

    const duration = performance.now() - start
    logger.logPerformance(operation, duration, context)
    return result
  } catch (error) {
    const duration = performance.now() - start
    logger.error(`${operation} failed after ${duration}ms`, {
      ...context,
      error: error instanceof Error ? error.message : 'Unknown error',
    })
    throw error
  }
}
