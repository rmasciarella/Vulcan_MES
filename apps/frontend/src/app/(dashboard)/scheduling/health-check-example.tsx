'use client'

import { ConnectionStatusIndicator } from '@/features/scheduling/components/connection-status-indicator'
import { useSupabaseHealth } from '@/shared/hooks/use-supabase-health'
import { Alert } from '@/shared/ui/alert'
import { useEffect } from 'react'

/**
 * Example dashboard component demonstrating health check integration
 * This shows different strategies for using the optimized health checks
 */
export function SchedulingDashboardWithHealth() {
  // Strategy 1: Passive monitoring (default - no database traffic)
  const passiveHealth = useSupabaseHealth()

  // Strategy 2: Active monitoring for critical dashboards
  const activeHealth = useSupabaseHealth({
    enableActiveMonitoring: true, // This enables health checks only while mounted
    checkOnMount: true,
    onConnectionChange: (isHealthy) => {
      if (!isHealthy) {
        // Show user notification about connection loss
        console.warn('Database connection lost - data may be stale')
      } else {
        console.info('Database connection restored')
      }
    }
  })

  // Strategy 3: On-demand checks for critical operations
  const handleCriticalOperation = async () => {
    // Check connection before critical operation
    const isHealthy = await activeHealth.checkNow()
    
    if (!isHealthy) {
      alert('Cannot perform operation - database connection lost')
      return
    }
    
    // Proceed with critical operation
    console.log('Performing critical operation...')
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Production Scheduling Dashboard</h1>
        
        {/* Connection indicator in header */}
        <ConnectionStatusIndicator 
          enableMonitoring={true}
          showStats={process.env.NODE_ENV === 'development'}
        />
      </div>

      {/* Connection warning */}
      {!activeHealth.isHealthy && (
        <Alert variant="destructive">
          Database connection lost. Data shown may be outdated. 
          Real-time updates are paused until connection is restored.
        </Alert>
      )}

      {/* Dashboard content */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border rounded-lg p-4">
          <h2 className="font-semibold mb-2">Passive Monitoring</h2>
          <p className="text-sm text-muted-foreground mb-2">
            No database traffic, uses WebSocket events
          </p>
          <div className="text-sm">
            Status: {passiveHealth.isHealthy ? '✅ Connected' : '❌ Disconnected'}
          </div>
        </div>

        <div className="border rounded-lg p-4">
          <h2 className="font-semibold mb-2">Active Monitoring</h2>
          <p className="text-sm text-muted-foreground mb-2">
            Periodic health checks while this dashboard is open
          </p>
          <div className="text-sm space-y-1">
            <div>Status: {activeHealth.isHealthy ? '✅ Connected' : '❌ Disconnected'}</div>
            <div>Last Check: {activeHealth.lastCheckTime?.toLocaleTimeString() || 'Never'}</div>
            {activeHealth.isChecking && <div>Checking...</div>}
          </div>
        </div>

        <div className="border rounded-lg p-4 md:col-span-2">
          <h2 className="font-semibold mb-2">On-Demand Checks</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Check connection before critical operations
          </p>
          <button
            onClick={handleCriticalOperation}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
            disabled={activeHealth.isChecking}
          >
            Perform Critical Operation
          </button>
        </div>
      </div>

      {/* Usage Guidelines */}
      <div className="border rounded-lg p-4 bg-muted/50">
        <h3 className="font-semibold mb-2">Health Check Strategy Guidelines</h3>
        <ul className="text-sm space-y-1 list-disc list-inside">
          <li>
            <strong>Default (No checks):</strong> Most pages - rely on WebSocket connection monitoring
          </li>
          <li>
            <strong>Active Monitoring:</strong> Critical dashboards that need real-time data accuracy
          </li>
          <li>
            <strong>On-Demand:</strong> Before operations that must succeed (e.g., scheduling runs)
          </li>
          <li>
            <strong>Configuration:</strong> Set NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK=true to enable globally
          </li>
        </ul>
      </div>
    </div>
  )
}