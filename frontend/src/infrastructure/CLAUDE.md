# Infrastructure - External Services

## Claude Assistant Rules for Infrastructure

1. **Repository implementations ONLY** - Domain interfaces implemented here with Supabase
2. **Data adapters required** - Convert between domain models and database rows
3. **Error handling critical** - Manufacturing data failures must be caught and logged
4. **Performance monitoring** - Track query times and connection health
5. **NO domain logic** - Pure infrastructure concerns only

## Essential Patterns

### Repository Implementation (Supabase)

```typescript
// ✅ Repository implementation in infrastructure
export class SupabaseJobRepository implements JobRepository {
  private adapter = new JobAdapter()

  async findById(id: JobId): Promise<Job | null> {
    const { data, error } = await supabase
      .from('production_jobs')
      .select('*')
      .eq('id', id.toString())
      .single()

    if (error) {
      if (error.code === 'PGRST116') return null // Not found
      throw new Error(`Failed to find job: ${error.message}`)
    }

    return this.adapter.toDomain(data)
  }

  async save(job: Job): Promise<void> {
    const dbJob = this.adapter.toPersistence(job)

    const { error } = await supabase.from('production_jobs').upsert(dbJob, { onConflict: 'id' })

    if (error) throw new Error(`Failed to save job: ${error.message}`)
  }
}
```

### Data Adapters (Critical for Type Safety)

```typescript
// ✅ Adapter converts between domain and database types
export class JobAdapter {
  toDomain(dbJob: Database['public']['Tables']['production_jobs']['Row']): Job {
    return Job.reconstitute({
      id: new JobId(dbJob.id),
      title: new JobTitle(dbJob.title),
      estimatedDuration: Duration.fromMinutes(dbJob.estimated_duration_minutes),
      priority: this.mapDbPriorityToDomain(dbJob.priority),
      status: this.mapDbStatusToDomain(dbJob.status),
      scheduledStartTime: dbJob.scheduled_start_time ? new Date(dbJob.scheduled_start_time) : null,
      createdAt: new Date(dbJob.created_at),
    })
  }

  toPersistence(job: Job): Database['public']['Tables']['production_jobs']['Insert'] {
    return {
      id: job.id.toString(),
      title: job.title.getValue(),
      estimated_duration_minutes: job.estimatedDuration.toMinutes(),
      priority: job.priority.getValue(),
      status: this.mapDomainStatusToDb(job.status),
      scheduled_start_time: job.scheduledStartTime?.toISOString() || null,
      updated_at: new Date().toISOString(),
    }
  }

  private mapDbPriorityToDomain(dbPriority: string): Priority {
    switch (dbPriority) {
      case 'low':
        return Priority.low()
      case 'medium':
        return Priority.medium()
      case 'high':
        return Priority.high()
      case 'urgent':
        return Priority.urgent()
      default:
        throw new Error(`Unknown priority: ${dbPriority}`)
    }
  }
}
```

### TanStack Query Configuration (Manufacturing Optimized)

```typescript
// ✅ Query client with manufacturing-appropriate settings
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds - production data changes frequently
      gcTime: 5 * 60 * 1000, // 5 minutes cache
      retry: (failureCount, error) => {
        // Don't retry client errors
        if (error instanceof Error && error.message.includes('4')) {
          return false
        }
        return failureCount < 3
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 1,
      onError: (error) => {
        console.error('Mutation error:', error)
        // Track manufacturing operation failures
      },
    },
  },
})

// ✅ Manufacturing-specific query keys
export const queryKeys = {
  jobs: ['jobs'] as const,
  jobsByStatus: (status: string) => ['jobs', 'status', status] as const,
  resources: ['resources'] as const,
  schedules: ['schedules'] as const,
  machineStatus: ['machine-status'] as const,
}
```

### External API Integration (OR-Tools Solver)

```typescript
// ✅ Solver API client with proper error handling
export class SolverApiClient {
  private baseUrl = process.env.SOLVER_API_URL || 'http://localhost:8080'
  private timeout = 30000 // 30 seconds for complex optimizations

  async optimizeSchedule(request: OptimizationRequest): Promise<OptimizationResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeout)

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/optimize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': process.env.SOLVER_API_KEY!,
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`Solver API error: ${response.status} ${response.statusText}`)
      }

      return response.json()
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('Optimization timeout - problem may be too complex')
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }
}

export const solverApi = new SolverApiClient()
```

## Manufacturing-Specific Patterns

### Complex Data Relationships

```typescript
// ✅ Load jobs with all related manufacturing data in one query
export class ManufacturingJobRepository implements JobRepository {
  async findSchedulable(timeWindow: TimeWindow): Promise<Job[]> {
    const { data, error } = await supabase
      .from('production_jobs')
      .select(
        `
        *,
        resources!inner(id, name, capacity),
        job_dependencies(dependent_job_id),
        materials(material_id, quantity_required),
        job_tasks(task_id, sequence, duration)
      `,
      )
      .eq('status', 'pending')
      .gte('scheduled_start_time', timeWindow.start.toISOString())
      .lte('scheduled_start_time', timeWindow.end.toISOString())
      .order('priority', { ascending: false })
      .order('created_at', { ascending: true })

    if (error) throw new SchedulingError(`Failed to fetch schedulable jobs: ${error.message}`)
    return data.map((row) => this.adapter.toDomain(row))
  }
}
```

### Batch Operations for Schedule Updates

```typescript
// ✅ Update multiple jobs atomically when rescheduling
export const batchUpdateJobs = async (updates: JobUpdate[]): Promise<void> => {
  const { error } = await supabase.rpc('batch_update_schedule', {
    job_updates: updates.map((u) => ({
      job_id: u.jobId,
      new_start_time: u.startTime,
      new_resource_id: u.resourceId,
      update_reason: u.reason,
    })),
  })

  if (error) {
    throw new SchedulingError(`Batch update failed: ${error.message}`)
  }
}
```

### Real-time Manufacturing Updates

```typescript
// ✅ Subscribe to production changes with proper cleanup
export const useManufacturingRealtime = () => {
  const queryClient = useQueryClient()

  useEffect(() => {
    const channel = supabase
      .channel('production-updates')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'production_jobs' },
        (payload) => {
          // Invalidate affected queries
          queryClient.invalidateQueries({ queryKey: ['jobs'] })
          queryClient.invalidateQueries({ queryKey: ['schedules'] })

          // Handle specific events
          if (payload.eventType === 'UPDATE' && payload.new.status === 'blocked') {
            // Show alert for blocked jobs
            toast.error(`Job ${payload.new.name} blocked: ${payload.new.block_reason}`)
          }
        },
      )
      .on('postgres_changes', { event: '*', schema: 'public', table: 'resources' }, (payload) => {
        queryClient.invalidateQueries({ queryKey: ['resources'] })
      })
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [queryClient])
}
```

### Manufacturing Query Patterns

```typescript
// ✅ Time-window queries for shift-based planning
export const getShiftJobs = async (shiftStart: Date, shiftEnd: Date) => {
  const { data, error } = await supabase
    .from('production_jobs')
    .select('*, resources!inner(*)')
    .or(
      `scheduled_start_time.gte.${shiftStart.toISOString()},scheduled_end_time.lte.${shiftEnd.toISOString()}`,
    )
    .order('scheduled_start_time')

  return data
}

// ✅ Resource utilization queries
export const getResourceUtilization = async (resourceId: string, timeWindow: TimeWindow) => {
  const { data } = await supabase.rpc('calculate_resource_utilization', {
    resource_id: resourceId,
    start_time: timeWindow.start,
    end_time: timeWindow.end,
  })

  return data
}
```

### TanStack Query Configuration for Manufacturing

```typescript
// ✅ Optimized cache times for production data
export const jobsQueryOptions = {
  queryKey: ['jobs'],
  queryFn: fetchJobs,
  staleTime: 30 * 1000, // 30 seconds - production data freshness
  gcTime: 5 * 60 * 1000, // 5 minutes - memory efficiency
  refetchInterval: 60 * 1000, // 1 minute - background updates
  refetchOnWindowFocus: true, // Update when operators switch screens
}

// ✅ Mutation with optimistic updates
export const useScheduleJob = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: scheduleJob,
    onMutate: async (newJob) => {
      // Cancel in-flight queries
      await queryClient.cancelQueries({ queryKey: ['jobs'] })

      // Optimistic update
      const previousJobs = queryClient.getQueryData(['jobs'])
      queryClient.setQueryData(['jobs'], (old) => [...old, newJob])

      return { previousJobs }
    },
    onError: (err, newJob, context) => {
      // Rollback on error
      queryClient.setQueryData(['jobs'], context.previousJobs)
      toast.error('Failed to schedule job')
    },
    onSettled: () => {
      // Always refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}
```

---

**Critical**: Infrastructure implements domain repository interfaces with Supabase. Use data adapters for type conversion. Handle errors gracefully - manufacturing system failures are production-critical. Monitor performance and connection health.
