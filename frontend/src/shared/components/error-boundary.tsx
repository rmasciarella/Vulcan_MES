'use client'

import React, { Component, ReactNode, ErrorInfo } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { Button } from '@/shared/ui/button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  onRetry?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to monitoring service in production
    if (process.env.NODE_ENV === 'production') {
      console.error('ErrorBoundary caught error:', {
        error: error.toString(),
        errorInfo: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
      })
      // TODO: Send to error monitoring service (e.g., Sentry)
    } else {
      console.error('ErrorBoundary caught error:', error, errorInfo)
    }

    this.props.onError?.(error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
    this.props.onRetry?.()
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex min-h-[400px] items-center justify-center p-8">
          <div className="w-full max-w-md space-y-4">
            <div className="flex items-center space-x-3 text-red-600">
              <AlertTriangle className="h-8 w-8" />
              <h2 className="text-2xl font-semibold">Production Error</h2>
            </div>

            <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
              <p className="text-red-800">
                An unexpected error occurred in the manufacturing system. This has been logged for
                investigation.
              </p>

              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="mt-4">
                  <summary className="cursor-pointer text-sm text-red-600 hover:underline">
                    Error Details (Development Only)
                  </summary>
                  <pre className="mt-2 overflow-auto rounded bg-red-100 p-2 text-xs text-red-700">
                    {this.state.error.stack}
                  </pre>
                </details>
              )}
            </div>

            <div className="flex space-x-3">
              <Button onClick={this.handleRetry} variant="destructive" size="sm">
                <RotateCcw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
              <Button onClick={() => window.location.reload()} variant="outline" size="sm">
                Reload Page
              </Button>
              <Button onClick={() => window.history.back()} variant="ghost" size="sm">
                Go Back
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Specialized error boundary for manufacturing components
 */
export function ManufacturingErrorBoundary({
  children,
  componentName,
  onError,
  onRetry,
}: {
  children: ReactNode
  componentName?: string
  onError?: (error: Error) => void
  onRetry?: () => void
}) {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        console.error(`Manufacturing component error in ${componentName}:`, error, errorInfo)
        onError?.(error)
      }}
      {...(onRetry !== undefined && { onRetry })}
      fallback={
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-red-500" />
          <h3 className="mb-2 font-medium text-red-900">Manufacturing System Error</h3>
          <p className="mb-4 text-sm text-red-700">
            {componentName ? `Error in ${componentName} component` : 'System component error'}
          </p>
          <p className="mb-4 text-xs text-red-600">
            Please contact system administrator if this error persists
          </p>
          {onRetry && (
            <Button onClick={onRetry} variant="outline" size="sm">
              <RotateCcw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          )}
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  )
}

/**
 * Query error boundary for data fetching errors
 */
export function QueryErrorBoundary({
  children,
  onRetry,
}: {
  children: ReactNode
  onRetry?: () => void
}) {
  return (
    <ErrorBoundary
      onError={(error) => {
        console.error('Query error:', error)
      }}
      {...(onRetry !== undefined && { onRetry })}
      fallback={
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
          <AlertTriangle className="mx-auto mb-2 h-6 w-6 text-red-500" />
          <h4 className="mb-1 font-medium text-red-900">Data Loading Error</h4>
          <p className="mb-3 text-sm text-red-700">
            Unable to load data. Please check your connection and try again.
          </p>
          {onRetry && (
            <Button onClick={onRetry} variant="outline" size="sm">
              <RotateCcw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          )}
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  )
}
