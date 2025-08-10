'use client'

import { useSupabaseHealth } from '@/shared/hooks/use-supabase-health'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { useEffect, useState } from 'react'

/**
 * Connection status indicator for scheduling dashboards
 * Shows the current database connection status and allows manual refresh
 * 
 * @example
 * // In a dashboard header
 * <ConnectionStatusIndicator enableMonitoring />
 * 
 * @example
 * // Minimal indicator without active monitoring
 * <ConnectionStatusIndicator />
 */
interface ConnectionStatusIndicatorProps {
  /**
   * Enable active health monitoring while this component is mounted
   * @default false
   */
  enableMonitoring?: boolean
  
  /**
   * Show detailed statistics in development mode
   * @default false
   */
  showStats?: boolean
  
  /**
   * Callback when connection state changes
   */
  onConnectionChange?: (isHealthy: boolean) => void
}

export function ConnectionStatusIndicator({
  enableMonitoring = false,
  showStats = false,
  onConnectionChange
}: ConnectionStatusIndicatorProps) {
  const { 
    isHealthy, 
    isChecking, 
    lastCheckTime, 
    checkNow,
    getStats 
  } = useSupabaseHealth({
    enableActiveMonitoring: enableMonitoring,
    onConnectionChange: onConnectionChange ?? ((() => {}) as (isHealthy: boolean) => void),
    checkOnMount: enableMonitoring
  })

  const [stats, setStats] = useState<ReturnType<typeof getStats> | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  useEffect(() => {
    if (showStats) {
      const interval = setInterval(() => {
        setStats(getStats())
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [showStats, getStats])

  const formatLastCheck = () => {
    if (!lastCheckTime) return 'Never'
    const seconds = Math.floor((Date.now() - lastCheckTime.getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    return `${hours}h ago`
  }

  return (
    <div className="flex items-center gap-2">
      {/* Connection Status Badge */}
      <Badge
        variant={isHealthy ? 'default' : 'destructive'}
        className="cursor-pointer"
        onClick={() => setShowDetails(!showDetails)}
      >
        <span className={`inline-block w-2 h-2 rounded-full mr-2 ${
          isHealthy ? 'bg-green-500' : 'bg-red-500'
        } ${isChecking ? 'animate-pulse' : ''}`} />
        {isHealthy ? 'Connected' : 'Disconnected'}
      </Badge>

      {/* Manual Check Button (shown on hover or when disconnected) */}
      {(!isHealthy || showDetails) && (
        <Button
          variant="ghost"
          size="sm"
          onClick={checkNow}
          disabled={isChecking}
          className="text-xs"
        >
          {isChecking ? 'Checking...' : 'Check Now'}
        </Button>
      )}

      {/* Detailed Status (Development/Debug) */}
      {showDetails && (
        <div className="absolute top-full left-0 mt-2 p-3 bg-background border rounded-lg shadow-lg z-50 text-sm">
          <div className="space-y-1">
            <div>Status: {isHealthy ? '✅ Healthy' : '❌ Unhealthy'}</div>
            <div>Last Check: {formatLastCheck()}</div>
            {enableMonitoring && <div>Monitoring: Active</div>}
            
            {/* Development Stats */}
            {showStats && stats && (
              <>
                <div className="pt-2 mt-2 border-t">
                  <div className="font-semibold mb-1">Debug Info:</div>
                  <div className="text-xs space-y-1 text-muted-foreground">
                    <div>Health Checks: {stats.config.enabled ? 'Enabled' : 'Disabled'}</div>
                    <div>Interval: {stats.config.intervalMs / 1000}s</div>
                    <div>Current Interval: {stats.state.currentIntervalMs / 1000}s</div>
                    <div>Failures: {stats.state.consecutiveFailures}</div>
                    <div>Listeners: {stats.listenerCount}</div>
                    <div>Timer Active: {stats.hasActiveTimer ? 'Yes' : 'No'}</div>
                    <div>Realtime: {stats.hasRealtimeChannel ? 'Connected' : 'Not Connected'}</div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Minimal connection indicator for non-critical pages
 * Only shows status when connection is lost
 */
export function MinimalConnectionIndicator() {
  const { isHealthy } = useSupabaseHealth()
  
  if (isHealthy) return null
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Badge variant="destructive" className="shadow-lg">
        <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2 animate-pulse" />
        Database connection lost
      </Badge>
    </div>
  )
}