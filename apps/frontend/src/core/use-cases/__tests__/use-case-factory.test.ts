import { describe, it, expect, beforeEach } from 'vitest'
import { UseCaseFactory } from '../use-case-factory'

function createMockSupabase() {
  return { from: () => ({ select: () => ({ then: (r: any) => r }) }) } as any
}

describe('UseCaseFactory', () => {
  beforeEach(() => {
    UseCaseFactory.reset()
  })

  it('returns singleton instance and lazily initializes use cases', async () => {
    const instance1 = UseCaseFactory.getInstance()
    const instance2 = UseCaseFactory.getInstance()
    expect(instance1).toBe(instance2)

    await UseCaseFactory.initialize(createMockSupabase())

    const jobs = await instance1.getJobUseCases()
    const machines = await instance1.getMachineUseCases()
    const operators = await instance1.getOperatorUseCases()
    const schedules = await instance1.getScheduleUseCases()

    expect(jobs).toBeDefined()
    expect(machines).toBeDefined()
    expect(operators).toBeDefined()
    expect(schedules).toBeDefined()
  })
})
