// Minimal, dependency-free helpers for use-jobs invalidation logic
// Keep types generic to avoid importing app-specific types

export type JobStatusLike = string

export interface JobsListFiltersLike {
  status?: JobStatusLike | JobStatusLike[]
  // other filters not needed for current helpers
}

// Determine if a queryKey is a jobs list key: ['jobs', 'list', filters?]
export function isJobsListKey(key: unknown): key is readonly unknown[] {
  return Array.isArray(key) && key[0] === 'jobs' && key[1] === 'list'
}

// Normalize status filter to array for comparison
export function normalizeStatusFilter(
  status?: JobStatusLike | JobStatusLike[],
): JobStatusLike[] | undefined {
  if (!status) return undefined
  return Array.isArray(status) ? status : [status]
}

// Check if a jobs list query's filters match a changed status
export function listKeyMatchesStatus(
  key: readonly unknown[],
  changedStatus?: JobStatusLike,
): boolean {
  try {
    // key shape: ['jobs','list', filters]
    const filters = ((key as any)[2] || {}) as JobsListFiltersLike
    const filterStatuses = normalizeStatusFilter(filters.status)
    if (!changedStatus) return true // no specific status => safe to invalidate list queries
    if (!filterStatuses || filterStatuses.length === 0) return true // unfiltered lists should refresh
    return filterStatuses.includes(changedStatus)
  } catch {
    return false
  }
}
