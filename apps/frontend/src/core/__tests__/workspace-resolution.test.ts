import { describe, it, expect } from 'vitest'

describe('Workspace Package Resolution', () => {
  it('should resolve @vulcan/domain workspace package', async () => {
    // Test that we can import from the workspace package
    const domainModule = await import('@vulcan/domain')
    
    // Verify that the module exports the expected namespaces
    expect(domainModule).toBeDefined()
    expect(domainModule.Jobs).toBeDefined()
    expect(domainModule.Tasks).toBeDefined()
    expect(domainModule.Resources).toBeDefined()
    expect(domainModule.Testing).toBeDefined()
  })


  it('should resolve local frontend domain modules', async () => {
    // Test that local domain modules can be resolved
    const jobsModule = await import('@/core/domains/jobs')
    const tasksModule = await import('@/core/domains/tasks')
    
    expect(jobsModule).toBeDefined()
    expect(tasksModule).toBeDefined()
    expect(tasksModule.Task).toBeDefined()
  })
})