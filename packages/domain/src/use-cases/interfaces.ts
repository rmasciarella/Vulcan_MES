// Shared domain use-case interfaces (DDD) for unified data access
// These interfaces are intentionally minimal and technology-agnostic.
// Concrete implementations live in application layers (e.g., frontend or API).

// Optional CQRS split: Query and Command interfaces per domain

// Jobs
export interface IJobQueries<TJob, TJobId = string> {
  getJobs(filters?: Record<string, unknown>): Promise<TJob[]>
  getJob(id: TJobId): Promise<TJob>
  getJobsByStatus(status: string): Promise<TJob[]>
  searchJobs(searchTerm: string): Promise<TJob[]>
  getJobCount(): Promise<Record<string, number> & { total: number }>
}

export interface IJobCommands<TJob, TJobId = string> {
  createJob(data: Record<string, unknown>): Promise<TJob>
  updateJob(id: TJobId, data: Record<string, unknown>): Promise<TJob>
  updateJobStatus(params: { id: TJobId; status: string }): Promise<TJob>
  deleteJob(id: TJobId): Promise<void>
  bulkUpdateStatus(updates: Array<{ id: TJobId; status: string }>): Promise<TJob[]>
}

export type IJobUseCases<TJob, TJobId = string> = IJobQueries<TJob, TJobId> & IJobCommands<TJob, TJobId>

// Schedules
export interface IScheduleQueries<TSchedule, TScheduleId = string, TScheduledTask = unknown> {
  fetchSchedules(filters?: Record<string, unknown>): Promise<TSchedule[]>
  fetchScheduleById(id: TScheduleId): Promise<TSchedule | null>
  fetchScheduleTasks(scheduleId: TScheduleId): Promise<TScheduledTask[]>
}

export interface IScheduleCommands<TSchedule, TScheduleId = string, TScheduledTask = unknown> {
  createSchedule(schedule: Record<string, unknown>): Promise<TSchedule>
  updateScheduleSolverStatus(id: TScheduleId, solverStatus: string): Promise<TSchedule>
  saveDraftSchedule(scheduleId: TScheduleId, tasks: TScheduledTask[]): Promise<{ scheduleId: string; taskCount: number }>
  deleteSchedule(id: TScheduleId): Promise<void>
}

export type IScheduleUseCases<TSchedule, TScheduleId = string, TScheduledTask = unknown> =
  IScheduleQueries<TSchedule, TScheduleId, TScheduledTask> & IScheduleCommands<TSchedule, TScheduleId, TScheduledTask>

// Operators
export interface IOperatorQueries<TOperator, TOperatorId = string> {
  getOperators(filters?: Record<string, unknown>): Promise<TOperator[]>
  getOperatorById(id: TOperatorId): Promise<TOperator>
}

export interface IOperatorCommands<TOperator, TOperatorId = string> {
  updateOperatorStatus(id: TOperatorId, status: string): Promise<TOperator>
  updateOperatorActiveStatus(id: TOperatorId, isActive: boolean): Promise<TOperator>
  createOperator(data: Record<string, unknown>): Promise<TOperator>
  deleteOperator(id: TOperatorId): Promise<void>
}

export type IOperatorUseCases<TOperator, TOperatorId = string> = IOperatorQueries<TOperator, TOperatorId> & IOperatorCommands<TOperator, TOperatorId>

// Machines
export interface IMachineQueries<TMachine, TMachineId = string> {
  getMachines(filters?: Record<string, unknown>): Promise<TMachine[]>
  getMachineById(id: TMachineId): Promise<TMachine>
}

export interface IMachineCommands<TMachine, TMachineId = string> {
  updateMachineStatus(id: TMachineId, status: string): Promise<TMachine>
  updateMachineActiveStatus(id: TMachineId, isActive: boolean): Promise<TMachine>
  createMachine(data: Record<string, unknown>): Promise<TMachine>
  deleteMachine(id: TMachineId): Promise<void>
}

export type IMachineUseCases<TMachine, TMachineId = string> = IMachineQueries<TMachine, TMachineId> & IMachineCommands<TMachine, TMachineId>

// Tasks
export interface ITaskQueries<TTask, TTaskId = string> {
  getTasks(filters?: Record<string, unknown>): Promise<TTask[]>
  getTask(id: TTaskId): Promise<TTask>
  getTaskById(id: TTaskId): Promise<TTask>
  getTasksByJobId(jobId: string): Promise<TTask[]>
  getTasksByStatus(status: string): Promise<TTask[]>
  getSchedulableTasks(): Promise<TTask[]>
  getActiveTasks(): Promise<TTask[]>
  getSetupTasks(): Promise<TTask[]>
  getTasksBySkillLevel(skillLevel: string): Promise<TTask[]>
  getUnattendedTasks(): Promise<TTask[]>
  getAttendedTasks(): Promise<TTask[]>
  getPaginatedTasks(pageSize: number, offset: number, filters?: Record<string, unknown>): Promise<{ tasks: TTask[]; total: number; hasMore: boolean }>
  getTaskCount(): Promise<Record<string, number> & { total: number }>
  validateTaskPrecedence(jobId: string): Promise<boolean>
}

export interface ITaskCommands<TTask, TTaskId = string> {
  createTask(data: Record<string, unknown>): Promise<TTask>
  updateTask(id: TTaskId, data: Record<string, unknown>): Promise<TTask>
  updateTaskStatus(id: TTaskId, status: string, reason?: string): Promise<TTask>
  deleteTask(id: TTaskId): Promise<void>
  markTaskReady(id: TTaskId): Promise<TTask>
  scheduleTask(id: TTaskId, scheduledAt: Date): Promise<TTask>
  startTask(id: TTaskId, startedAt?: Date): Promise<TTask>
  completeTask(id: TTaskId, completedAt?: Date): Promise<TTask>
  cancelTask(id: TTaskId, reason: string): Promise<TTask>
}

export type ITaskUseCases<TTask, TTaskId = string> = ITaskQueries<TTask, TTaskId> & ITaskCommands<TTask, TTaskId>
