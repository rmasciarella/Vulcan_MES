import { Jobs, Testing } from '@vulcan/domain'

export function makeJob(overrides: Partial<{
  id: string
  name: string
  priority: Jobs.JobPriority
}> = {}) {
  return Testing.createMockWorkOrder({
    id: overrides.id ?? '550e8400-e29b-41d4-a716-446655440021',
    name: overrides.name ?? 'Test Job',
    priority: overrides.priority ?? Jobs.JobPriority.MEDIUM,
  })
}
