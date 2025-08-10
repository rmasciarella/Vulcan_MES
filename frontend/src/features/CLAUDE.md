# Features - Feature Modules

## Claude Assistant Rules for Features

1. **Self-contained modules** - Each feature has components/, hooks/, stores/, utils/, api/
2. **NO cross-feature imports** - Features communicate through events or shared context only
3. **Export public API** - Feature index.ts exports only what other parts need
4. **TanStack Query for server state** - Zustand only for UI state
5. **Manufacturing performance first** - Use virtualization for large datasets

## Feature Structure Example

### Job Scheduling Feature

```typescript
// features/job-scheduling/index.ts - Public API
export { JobSchedulingWidget } from './components/JobSchedulingWidget'
export { useJobScheduling } from './hooks/useJobScheduling'
export type { SchedulingConfig } from './types'

// features/job-scheduling/hooks/useJobScheduling.ts
export function useJobScheduling() {
  // ✅ TanStack Query for server state
  const jobsQuery = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    staleTime: 30 * 1000, // 30 seconds for manufacturing data
  })

  // ✅ Zustand for UI state only
  const { selectedJob, setSelectedJob } = useSchedulingStore()

  const scheduleJob = useMutation({
    mutationFn: scheduleJobApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  return {
    jobs: jobsQuery.data ?? [],
    isLoading: jobsQuery.isLoading,
    selectedJob,
    setSelectedJob,
    scheduleJob: scheduleJob.mutate,
  }
}
```

### Zustand Store (UI State Only)

```typescript
// features/job-scheduling/stores/schedulingStore.ts
interface SchedulingState {
  selectedJob: Job | null
  viewMode: 'table' | 'gantt'
  filters: JobFilters

  selectJob: (job: Job | null) => void
  setViewMode: (mode: 'table' | 'gantt') => void
  setFilters: (filters: JobFilters) => void
}

export const useSchedulingStore = create<SchedulingState>((set) => ({
  selectedJob: null,
  viewMode: 'table',
  filters: { status: [], priority: [] },

  selectJob: (job) => set({ selectedJob: job }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setFilters: (filters) => set({ filters }),
}))
```

### Feature Components (Manufacturing Optimized)

```typescript
// features/job-scheduling/components/JobSchedulingWidget.tsx
'use client';
import { useJobScheduling } from '../hooks/useJobScheduling';
import { VirtualizedJobTable } from '@/shared/ui/VirtualizedTable';

export function JobSchedulingWidget() {
  const {
    jobs,
    isLoading,
    scheduleJob,
    selectedJob,
    viewMode,
    setViewMode,
  } = useJobScheduling();

  // ✅ Use virtualization for large datasets (>100 jobs)
  const JobTable = jobs.length > 100 ? VirtualizedJobTable : RegularJobTable;

  if (isLoading) return <JobTableSkeleton />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <h2>Job Scheduling</h2>
        <ViewModeToggle value={viewMode} onChange={setViewMode} />
      </div>

      <JobTable
        jobs={jobs}
        onScheduleJob={scheduleJob}
        selectedJob={selectedJob}
      />
    </div>
  );
}
```

### Cross-Feature Communication (Event Bus Only)

```typescript
// shared/lib/eventBus.ts - Simple event system
type EventMap = {
  'job-scheduled': { jobId: string; startTime: Date }
  'resource-allocated': { resourceId: string; jobId: string }
}

export const eventBus = {
  emit<K extends keyof EventMap>(event: K, data: EventMap[K]) {
    window.dispatchEvent(new CustomEvent(event, { detail: data }))
  },

  on<K extends keyof EventMap>(event: K, handler: (data: EventMap[K]) => void) {
    const listener = (e: CustomEvent) => handler(e.detail)
    window.addEventListener(event, listener as EventListener)
    return () => window.removeEventListener(event, listener as EventListener)
  },
}

// In feature hooks
useEffect(() => {
  const unsubscribe = eventBus.on('resource-allocated', () => {
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
  })
  return unsubscribe
}, [])
```

## Performance Optimizations

```typescript
// Virtualization for Large Job Lists
import { useVirtualizer } from '@tanstack/react-virtual';

// Use for lists >100 items
const virtualizer = useVirtualizer({
  count: jobs.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 50,
  overscan: 20,
});

// Manufacturing-specific row optimizations
const JobRow = React.memo(({ job, style }: JobRowProps) => {
  return (
    <div style={style} className="flex items-center p-4 border-b">
      <span className="flex-1">{job.name}</span>
      <span className="w-32">{job.dueDate}</span>
      <JobStatus status={job.status} />
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison for manufacturing data
  return prevProps.job.id === nextProps.job.id &&
         prevProps.job.status === nextProps.job.status;
});

// Debounced search for job filtering
const useDebounce = (value: string, delay: number) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
};
```

---

**Critical**: Features are self-contained modules for manufacturing capabilities. Use TanStack Query for server state, Zustand for UI state. NO cross-feature imports. Use virtualization for large datasets (>100 items).
