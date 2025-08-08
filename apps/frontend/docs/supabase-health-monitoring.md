# Supabase Health Check Optimization Guide

## Overview

The Supabase browser singleton has been optimized to minimize unnecessary database traffic while maintaining connection reliability. The previous implementation was hitting the departments table every 30 seconds, causing constant traffic. The new implementation provides multiple strategies for health monitoring with configurable, opt-in behavior.

## Key Improvements

### 1. **Opt-in Health Checks**
- Health checks are now **disabled by default**
- Enable via environment variable: `NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK=true`
- Can be enabled dynamically for specific dashboards/components

### 2. **Multiple Monitoring Strategies**

#### Passive Monitoring (Default)
- **Zero database traffic**
- Uses Supabase WebSocket connection events
- Monitors auth state changes
- Suitable for most pages and components

```typescript
// No configuration needed - this is the default
const { isHealthy } = useSupabaseHealth()
```

#### Active Monitoring (Opt-in)
- Periodic health checks only while component is mounted
- Configurable intervals (default: 5 minutes)
- Exponential backoff on failures (up to 1 hour)
- Use for critical dashboards requiring real-time accuracy

```typescript
const { isHealthy } = useSupabaseHealth({
  enableActiveMonitoring: true,
  onConnectionChange: (healthy) => {
    // Handle connection state changes
  }
})
```

#### On-Demand Checks
- Manual health checks before critical operations
- No periodic polling
- Ensures connection before important transactions

```typescript
const { checkNow } = useSupabaseHealth()

const handleCriticalOperation = async () => {
  const isHealthy = await checkNow()
  if (!isHealthy) {
    // Handle connection failure
    return
  }
  // Proceed with operation
}
```

### 3. **Lightweight Health Checks**
- Uses custom `ping()` RPC function instead of table queries
- Falls back to system tables only if RPC unavailable
- Significantly reduces database load

### 4. **Exponential Backoff**
- Failed connections increase check intervals
- Reduces traffic during outages
- Automatic recovery when connection restored

## Configuration

### Environment Variables

```bash
# Enable/disable health checks globally (default: false)
NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK=false

# Health check interval in milliseconds (default: 300000 = 5 minutes)
NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS=300000

# Maximum interval with exponential backoff (default: 3600000 = 1 hour)
NEXT_PUBLIC_DB_HEALTH_CHECK_MAX_INTERVAL_MS=3600000
```

### Database Setup

Run the migration to create the lightweight ping function:

```sql
-- Create in supabase/migrations/
CREATE OR REPLACE FUNCTION public.ping()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT 'pong'::text;
$$;
```

## Usage Examples

### 1. Critical Dashboard with Active Monitoring

```typescript
import { ConnectionStatusIndicator } from '@/features/scheduling/components/connection-status-indicator'

export function CriticalDashboard() {
  return (
    <div>
      <header>
        <h1>Production Scheduling</h1>
        <ConnectionStatusIndicator enableMonitoring />
      </header>
      {/* Dashboard content */}
    </div>
  )
}
```

### 2. Regular Page with Passive Monitoring

```typescript
import { MinimalConnectionIndicator } from '@/features/scheduling/components/connection-status-indicator'

export function RegularPage() {
  return (
    <div>
      {/* Page content */}
      <MinimalConnectionIndicator />
    </div>
  )
}
```

### 3. Form with Pre-Submit Health Check

```typescript
export function SchedulingForm() {
  const { checkNow, isHealthy } = useSupabaseHealth()
  
  const handleSubmit = async (data) => {
    // Check connection before submitting
    if (!await checkNow()) {
      toast.error('Cannot submit - database connection lost')
      return
    }
    
    // Submit form
    await submitSchedule(data)
  }
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      <button type="submit" disabled={!isHealthy}>
        Submit Schedule
      </button>
    </form>
  )
}
```

## Performance Impact

### Before Optimization
- **30-second intervals** hitting departments table
- **2,880 queries/day** per browser tab
- Constant database traffic even on idle pages

### After Optimization
- **Default: 0 queries** (WebSocket monitoring only)
- **Active monitoring: 288 queries/day** (5-minute intervals)
- **With backoff: <100 queries/day** during connection issues
- Queries only on pages that need them

## Best Practices

1. **Use passive monitoring by default** - Most pages don't need active health checks
2. **Enable active monitoring only for critical dashboards** - Production scheduling, real-time monitoring
3. **Use on-demand checks for critical operations** - Before scheduling runs, data submissions
4. **Configure intervals based on criticality** - Longer intervals for less critical systems
5. **Monitor in development, disable in production** - Unless specifically needed

## Migration Guide

### Step 1: Update Environment Variables
```bash
# Disable health checks by default
NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK=false

# Or enable with longer intervals
NEXT_PUBLIC_ENABLE_DB_HEALTH_CHECK=true
NEXT_PUBLIC_DB_HEALTH_CHECK_INTERVAL_MS=600000  # 10 minutes
```

### Step 2: Run Database Migration
```bash
supabase migration up
```

### Step 3: Update Critical Components
```typescript
// Before
const client = getSupabaseBrowserClient()
const isHealthy = isSupabaseConnectionHealthy() // This triggered checks

// After
const { isHealthy } = useSupabaseHealth({
  enableActiveMonitoring: true  // Only for critical components
})
```

## Monitoring and Debugging

### View Connection Statistics
```typescript
const { getStats } = useSupabaseHealth()
const stats = getStats()

console.log({
  enabled: stats.config.enabled,
  interval: stats.config.intervalMs,
  failures: stats.state.consecutiveFailures,
  lastCheck: stats.state.lastCheckTime
})
```

### Enable Debug Mode in Development
```typescript
<ConnectionStatusIndicator 
  enableMonitoring={true}
  showStats={process.env.NODE_ENV === 'development'}
/>
```

## Troubleshooting

### Issue: Health checks still running when disabled
**Solution:** Check if any component has `enableActiveMonitoring: true`

### Issue: Connection shows as unhealthy but database works
**Solution:** Check if ping() function exists in database

### Issue: Too many connection state changes
**Solution:** Increase debounce time or use passive monitoring only

## Summary

The optimized health check system provides:
- **80-99% reduction in database traffic**
- **Configurable monitoring strategies**
- **Better performance during connection issues**
- **Granular control per component**
- **Zero traffic by default**

This approach maintains connection reliability while significantly reducing unnecessary database load, especially important for production environments with many concurrent users.