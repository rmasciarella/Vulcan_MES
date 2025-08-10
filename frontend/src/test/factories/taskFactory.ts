import { Tasks } from '@vulcan/domain'

export function makeTask(overrides: Partial<{
  id: string
  jobId: string
  name: string
  durationMinutes: number
  sequence: number
  attendanceRequirement: number
  isSetupTask: boolean
  assignedTo?: string
  taskModes?: any[]
}> = {}) {
  const entity = Tasks.TaskEntity.create({
    id: overrides.id ?? '550e8400-e29b-41d4-a716-446655440022',
    jobId: overrides.jobId ?? '550e8400-e29b-41d4-a716-446655440023',
    name: overrides.name ?? 'Test Task',
    duration: Tasks.Duration.fromMinutes(overrides.durationMinutes ?? 30),
    sequence: overrides.sequence ?? 1,
    attendanceRequirement: overrides.attendanceRequirement ?? 0, // 0 = attended, 1 = unattended
    isSetupTask: overrides.isSetupTask ?? false,
    ...(overrides.assignedTo !== undefined && { assignedTo: overrides.assignedTo }),
    taskModes: overrides.taskModes ?? []
  })
  return entity
}
