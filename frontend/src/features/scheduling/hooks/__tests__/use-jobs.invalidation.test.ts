import { describe, expect, it } from 'vitest'
import { isJobsListKey, listKeyMatchesStatus } from '../use-jobs-helpers'

// Helper to build list keys like the hook does
const listKey = (filters: any) => ['jobs', 'list', filters] as const

describe('use-jobs invalidation helpers', () => {
  it('isJobsListKey identifies list query keys', () => {
    expect(isJobsListKey(['jobs', 'list'])).toBe(true)
    expect(isJobsListKey(['jobs', 'list', {}])).toBe(true)
    expect(isJobsListKey(['jobs', 'detail', 'id'])).toBe(false)
    expect(isJobsListKey(['other'])).toBe(false)
    expect(isJobsListKey('not-an-array')).toBe(false)
  })

  it('listKeyMatchesStatus returns true for unfiltered lists', () => {
    expect(listKeyMatchesStatus(listKey({}), 'SCHEDULED' as any)).toBe(true)
    expect(listKeyMatchesStatus(listKey({ status: undefined }), 'SCHEDULED' as any)).toBe(true)
  })

  it('listKeyMatchesStatus matches single status filters', () => {
    expect(listKeyMatchesStatus(listKey({ status: 'SCHEDULED' }), 'SCHEDULED' as any)).toBe(true)
    expect(listKeyMatchesStatus(listKey({ status: 'DRAFT' }), 'SCHEDULED' as any)).toBe(false)
  })

  it('listKeyMatchesStatus matches array status filters', () => {
    expect(listKeyMatchesStatus(listKey({ status: ['SCHEDULED', 'IN_PROGRESS'] }), 'SCHEDULED' as any)).toBe(true)
    expect(listKeyMatchesStatus(listKey({ status: ['DRAFT', 'COMPLETED'] }), 'SCHEDULED' as any)).toBe(false)
  })

  it('listKeyMatchesStatus returns true when changedStatus is undefined (safety refresh)', () => {
    expect(listKeyMatchesStatus(listKey({ status: ['DRAFT'] }), undefined)).toBe(true)
  })
})

