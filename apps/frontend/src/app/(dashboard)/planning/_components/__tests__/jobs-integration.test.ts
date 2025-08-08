/**
 * Integration test to verify Jobs domain integration with UI components
 * This test validates that the domain objects work correctly with the UI layer
 */

import { describe, it, expect, vi } from 'vitest'
import { Jobs } from '@vulcan/domain'

// Mock Supabase client to avoid actual database calls in tests
vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({
          single: vi.fn(() => Promise.resolve({ data: null, error: null }))
        }))
      }))
    }))
  }))
}))

describe('Jobs Domain Integration', () => {
  it('should create a Job entity with minimal required fields', () => {
    // Act: Create a job using the domain factory method
    const job = Jobs.JobEntity.create({
      id: 'job-001',
      name: 'Laser Assembly',
      priority: Jobs.JobPriority.MEDIUM,
    })

    // Assert: Verify job properties are accessible in the expected format
    expect(job.id).toBe('job-001')
    expect(job.name).toBe('Laser Assembly')
    expect(job.status).toBe(Jobs.JobStatus.PENDING)
    expect(job.priority).toBe(Jobs.JobPriority.MEDIUM)
    expect(job.createdAt).toBeInstanceOf(Date)
    expect(job.updatedAt).toBeInstanceOf(Date)
  })

  it('should handle job status transitions correctly', () => {
    const job = Jobs.JobEntity.create({ id: 'job-002', name: 'Assembly Unit', priority: Jobs.JobPriority.LOW })

    expect(job.status).toBe(Jobs.JobStatus.PENDING)

    job.updateStatus(Jobs.JobStatus.IN_PROGRESS)
    expect(job.status).toBe(Jobs.JobStatus.IN_PROGRESS)

    job.updateStatus(Jobs.JobStatus.COMPLETED)
    expect(job.status).toBe(Jobs.JobStatus.COMPLETED)
  })
})
