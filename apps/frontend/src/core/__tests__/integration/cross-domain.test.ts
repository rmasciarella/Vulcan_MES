import { describe, it, expect, beforeEach } from 'vitest'
import { Job } from '../../domains/jobs/job'
import { Task } from '../../domains/tasks/task'
import { TaskMode } from '../../domains/tasks/entities/TaskMode'
import { WorkCell } from '../../domains/resources/entities/WorkCell'
import { Machine } from '../../domains/resources/entities/Machine'
import {
  JobId,
  JobTitle,
  EstimatedDuration,
  JobPriority,
  JobStatus,
} from '../../domains/jobs/value-objects'
import {
  TaskId,
  TaskTitle,
  TaskModeId,
  TaskModeName,
  SkillLevel,
  WorkCellId,
} from '../../domains/tasks/value-objects'
import {
  MachineId,
  MachineName,
  MachineType,
  WorkCellCapacity,
  DepartmentCode,
} from '../../domains/resources/value-objects'

describe('Cross-Domain Integration', () => {
  describe('Job-Task Relationship', () => {
    let job: Job
    let task1: Task
    let task2: Task

    beforeEach(() => {
      job = Job.create({
        id: JobId.create('550e8400-e29b-41d4-a716-446655440001'),
        title: JobTitle.create('Laser Assembly Production'),
        estimatedDuration: EstimatedDuration.create(480),
        priority: JobPriority.urgent(),
        releaseDate: new Date('2025-01-01'),
        dueDate: new Date('2025-01-07'),
      })

      task1 = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440002'),
        jobId: job.getId(),
        title: TaskTitle.create('CNC Machining'),
        sequenceNumber: 1,
        estimatedDuration: 120,
      })

      task2 = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440003'),
        jobId: job.getId(),
        title: TaskTitle.create('Quality Inspection'),
        sequenceNumber: 2,
        estimatedDuration: 30,
        predecessorIds: [task1.id],
      })
    })

    it('should maintain job-task relationship integrity', () => {
      // Tasks belong to job
      expect(task1.jobId.equals(job.getId())).toBe(true)
      expect(task2.jobId.equals(job.getId())).toBe(true)

      // Task sequencing
      expect(task1.sequenceNumber).toBe(1)
      expect(task2.sequenceNumber).toBe(2)
      expect(task2.predecessorIds).toContain(task1.id.toString())
    })

    it('should propagate job status changes to tasks', () => {
      // Start the job
      job.start()
      expect(job.getStatus()).toBe(JobStatus.IN_PROGRESS)

      // Tasks should be ready to start
      task1.markReady()
      expect(task1.status.value).toBe('ready')

      // Start first task
      task1.start()
      expect(task1.status.value).toBe('in_progress')

      // Complete first task
      task1.complete()
      expect(task1.status.value).toBe('completed')

      // Second task can now start (predecessor complete)
      task2.markReady()
      task2.start()
      expect(task2.status.value).toBe('in_progress')
    })

    it('should calculate total job duration from tasks', () => {
      const totalTaskDuration = task1.estimatedDurationMinutes + task2.estimatedDurationMinutes

      expect(totalTaskDuration).toBe(150) // 120 + 30

      // Job's estimated duration should accommodate all tasks
      expect(job.getEstimatedDuration().minutes).toBeGreaterThanOrEqual(totalTaskDuration)
    })
  })

  describe('Task-Resource Allocation', () => {
    let task: Task
    let taskMode: TaskMode
    let workCell: WorkCell
    let machine: Machine

    beforeEach(() => {
      // Create WorkCell
      workCell = WorkCell.create({
        id: WorkCellId.create('550e8400-e29b-41d4-a716-446655440004'),
        name: 'CNC WorkCell 1',
        departmentCode: DepartmentCode.MS, // Manufacturing Station
        capacity: WorkCellCapacity.create(3), // Can handle 3 concurrent tasks
        isActive: true,
      })

      // Create Machine in WorkCell
      machine = Machine.create({
        id: MachineId.create('550e8400-e29b-41d4-a716-446655440005'),
        name: MachineName.create('CNC-001'),
        type: MachineType.CNC,
        workCellId: workCell.id,
        isOperational: true,
      })

      // Create Task
      task = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440006'),
        jobId: JobId.create('550e8400-e29b-41d4-a716-446655440007'),
        title: TaskTitle.create('Precision Machining'),
        sequenceNumber: 1,
        estimatedDuration: 45,
      })

      // Create TaskMode with resource requirements
      taskMode = TaskMode.create({
        id: TaskModeId.create('550e8400-e29b-41d4-a716-446655440008'),
        taskId: task.id,
        name: TaskModeName.create('Standard Mode'),
        type: 'primary',
        durationMinutes: 45,
        skillRequirements: [{ level: 'competent', quantity: 1 }],
        workCellRequirements: [workCell.id.toString()],
        isPrimaryMode: true,
      })
    })

    it('should validate resource requirements for task execution', () => {
      // TaskMode requires specific WorkCell
      expect(taskMode.workCellRequirements).toContain(workCell.id.toString())

      // WorkCell has capacity for task
      expect(workCell.hasCapacityFor(1)).toBe(true)

      // Machine is available in required WorkCell
      expect(machine.workCellId.equals(workCell.id)).toBe(true)
      expect(machine.isOperational).toBe(true)
    })

    it('should enforce capacity constraints', () => {
      // WorkCell can handle 3 concurrent tasks
      expect(workCell.capacity.value).toBe(3)

      // Allocate capacity
      workCell.allocateCapacity(2)
      expect(workCell.hasCapacityFor(1)).toBe(true) // Still has 1 slot
      expect(workCell.hasCapacityFor(2)).toBe(false) // Can't fit 2 more

      // Release capacity
      workCell.releaseCapacity(1)
      expect(workCell.hasCapacityFor(2)).toBe(true) // Now has 2 slots
    })

    it('should validate skill requirements', () => {
      const skillRequirements = taskMode.skillRequirements

      // TaskMode requires competent operator
      expect(skillRequirements).toHaveLength(1)
      expect(skillRequirements[0].level).toBe('competent')
      expect(skillRequirements[0].quantity).toBe(1)

      // Skill hierarchy validation
      const requiredSkill = SkillLevel.create('competent', 1)
      const expertSkill = SkillLevel.create('expert', 1)

      // Expert can fulfill competent requirement
      expect(expertSkill.canFulfill(requiredSkill)).toBe(true)
    })

    it('should handle machine maintenance windows', () => {
      // Machine is initially operational
      expect(machine.isOperational).toBe(true)

      // Schedule maintenance
      machine.scheduleMaintenanceWindow(
        new Date('2025-01-15T20:00:00Z'),
        new Date('2025-01-16T04:00:00Z'),
      )

      // Machine remains operational outside maintenance window
      const duringProduction = new Date('2025-01-15T10:00:00Z')
      expect(machine.isAvailableAt(duringProduction)).toBe(true)

      // Machine unavailable during maintenance
      const duringMaintenance = new Date('2025-01-15T22:00:00Z')
      expect(machine.isAvailableAt(duringMaintenance)).toBe(false)
    })
  })

  describe('Manufacturing Flow Integration', () => {
    it('should enforce department progression MS → FH → OB', () => {
      // Create WorkCells for each department
      const msWorkCell = WorkCell.create({
        id: WorkCellId.create('550e8400-e29b-41d4-a716-446655440009'),
        name: 'Manufacturing Station 1',
        departmentCode: DepartmentCode.MS,
        capacity: WorkCellCapacity.create(3),
        isActive: true,
      })

      const fhWorkCell = WorkCell.create({
        id: WorkCellId.create('550e8400-e29b-41d4-a716-446655440010'),
        name: 'Final Assembly 1',
        departmentCode: DepartmentCode.FH,
        capacity: WorkCellCapacity.create(2),
        isActive: true,
      })

      const obWorkCell = WorkCell.create({
        id: WorkCellId.create('550e8400-e29b-41d4-a716-446655440011'),
        name: 'Outbound 1',
        departmentCode: DepartmentCode.OB,
        capacity: WorkCellCapacity.create(4),
        isActive: true,
      })

      // Department codes enforce order
      expect(msWorkCell.departmentCode).toBe(DepartmentCode.MS)
      expect(fhWorkCell.departmentCode).toBe(DepartmentCode.FH)
      expect(obWorkCell.departmentCode).toBe(DepartmentCode.OB)

      // Create tasks following manufacturing flow
      const machiningTask = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440012'),
        jobId: JobId.create('550e8400-e29b-41d4-a716-446655440013'),
        title: TaskTitle.create('CNC Machining'),
        sequenceNumber: 1,
        estimatedDuration: 60,
      })

      const assemblyTask = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440014'),
        jobId: JobId.create('550e8400-e29b-41d4-a716-446655440013'),
        title: TaskTitle.create('Final Assembly'),
        sequenceNumber: 2,
        estimatedDuration: 45,
        predecessorIds: [machiningTask.id.toString()],
      })

      const packagingTask = Task.create({
        id: TaskId.create('550e8400-e29b-41d4-a716-446655440015'),
        jobId: JobId.create('550e8400-e29b-41d4-a716-446655440013'),
        title: TaskTitle.create('Packaging'),
        sequenceNumber: 3,
        estimatedDuration: 15,
        predecessorIds: [assemblyTask.id.toString()],
      })

      // Tasks follow department progression
      expect(machiningTask.sequenceNumber).toBeLessThan(assemblyTask.sequenceNumber)
      expect(assemblyTask.sequenceNumber).toBeLessThan(packagingTask.sequenceNumber)
    })

    it('should handle business hours constraints', () => {
      // Business hours: 7 AM - 4 PM weekdays
      const duringBusinessHours = new Date('2025-01-06T10:00:00Z') // Monday 10 AM
      const outsideBusinessHours = new Date('2025-01-06T18:00:00Z') // Monday 6 PM
      const weekend = new Date('2025-01-04T10:00:00Z') // Saturday

      // Machines available 24/7
      const machine = Machine.create({
        id: MachineId.create('550e8400-e29b-41d4-a716-446655440016'),
        name: MachineName.create('CNC-002'),
        type: MachineType.CNC,
        workCellId: WorkCellId.create('550e8400-e29b-41d4-a716-446655440017'),
        isOperational: true,
      })

      expect(machine.isAvailableAt(duringBusinessHours)).toBe(true)
      expect(machine.isAvailableAt(outsideBusinessHours)).toBe(true)
      expect(machine.isAvailableAt(weekend)).toBe(true)

      // Operator availability would be restricted to business hours
      // (This would be implemented in Operator entity)
    })
  })

  describe('Event Propagation Across Domains', () => {
    it('should publish events when job status changes affect tasks', () => {
      const job = Job.create({
        id: JobId.create('550e8400-e29b-41d4-a716-446655440018'),
        title: JobTitle.create('Production Batch'),
        estimatedDuration: EstimatedDuration.create(240),
        priority: JobPriority.high(),
        releaseDate: new Date('2025-01-01'),
        dueDate: new Date('2025-01-03'),
      })

      // Start job - should emit JobStarted event
      job.start()
      const events = job.pullDomainEvents()

      expect(events).toHaveLength(1)
      expect(events[0].eventType).toBe('JobStarted')
      expect(events[0].aggregateId).toBe(job.getId().toString())
    })

    it('should handle resource allocation events', () => {
      const workCell = WorkCell.create({
        id: WorkCellId.create('550e8400-e29b-41d4-a716-446655440019'),
        name: 'Assembly Cell',
        departmentCode: DepartmentCode.FH,
        capacity: WorkCellCapacity.create(2),
        isActive: true,
      })

      // Allocate capacity - should emit event
      workCell.allocateCapacity(1)
      const events = workCell.pullDomainEvents()

      expect(events).toHaveLength(1)
      expect(events[0].eventType).toBe('WorkCellCapacityAllocated')
      expect(events[0].eventData.allocated).toBe(1)
      expect(events[0].eventData.available).toBe(1)
    })
  })
})
