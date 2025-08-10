// Task domain types for scheduling feature
// Consolidated from core/domains/tasks.ts

export enum TaskStatusValue {
  NOT_READY = 'not_ready',
  READY = 'ready',
  SCHEDULED = 'scheduled',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  ON_HOLD = 'on_hold',
  CANCELLED = 'cancelled',
}

export class TaskStatus {
  constructor(private _value: TaskStatusValue) {}
  
  getValue(): TaskStatusValue {
    return this._value
  }
  
  get value(): TaskStatusValue {
    return this._value
  }
  
  toString(): string {
    return this._value
  }
  
  static create(value: TaskStatusValue): TaskStatus {
    return new TaskStatus(value)
  }
}

export class TaskId {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskId {
    return new TaskId(value)
  }
}

export class TaskModeId {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskModeId {
    return new TaskModeId(value)
  }
}

export class TaskModeName {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskModeName {
    return new TaskModeName(value)
  }
}

export class TaskMode {
  constructor(
    public id: TaskModeId,
    public name: TaskModeName,
    public description: string,
  ) {}
  
  static create(params: {
    id: string
    name: string
    description: string
  }): TaskMode {
    return new TaskMode(
      TaskModeId.create(params.id),
      TaskModeName.create(params.name),
      params.description,
    )
  }
}

export class TaskName {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskName {
    return new TaskName(value)
  }
}

export class TaskSequence {
  constructor(private _value: number) {}
  
  get value(): number {
    return this._value
  }
  
  static create(value: number): TaskSequence {
    return new TaskSequence(value)
  }
}

export class AttendanceRequirement {
  constructor(private _isUnattended: boolean) {}
  
  get isUnattended(): boolean {
    return this._isUnattended
  }
  
  get isAttended(): boolean {
    return !this._isUnattended
  }
  
  static create(isUnattended: boolean): AttendanceRequirement {
    return new AttendanceRequirement(isUnattended)
  }
}

// Enhanced Task entity with all required properties
export class Task {
  constructor(
    public id: TaskId,
    public name: TaskName,
    public status: TaskStatus,
    public jobId: string,
    public sequence: TaskSequence,
    public attendanceRequirement: AttendanceRequirement,
    public isSetupTask: boolean,
    public skills: string[] = [],
    public workCells: string[] = [],
    public taskModes: any[] = [], // TaskMode interface would be defined separately
    public createdAt: Date = new Date(),
    public updatedAt: Date = new Date(),
  ) {}
  
  // Methods expected by the UI components
  areTaskModesLoaded(): boolean {
    return this.taskModes && this.taskModes.length > 0
  }
  
  getPrimaryMode(): any | null {
    return this.taskModes.find(mode => mode.isPrimary) || this.taskModes[0] || null
  }
  
  hasMultipleModes(): boolean {
    return this.taskModes.length > 1
  }
  
  static create(params: {
    id: string
    name: string
    status: TaskStatusValue
    jobId: string
    sequence: number
    isUnattended: boolean
    isSetupTask: boolean
    skills?: string[]
    workCells?: string[]
    taskModes?: any[]
  }): Task {
    return new Task(
      TaskId.create(params.id),
      TaskName.create(params.name),
      TaskStatus.create(params.status),
      params.jobId,
      TaskSequence.create(params.sequence),
      AttendanceRequirement.create(params.isUnattended),
      params.isSetupTask,
      params.skills || [],
      params.workCells || [],
      params.taskModes || [],
    )
  }
  
  static fromPersistence(params: {
    id: TaskId
    jobId: any // JobId type
    name: TaskName
    sequence: TaskSequence
    status: TaskStatus
    attendanceRequirement: AttendanceRequirement
    isSetupTask: boolean
    taskModes?: any[]
    createdAt: Date
    updatedAt: Date
    version?: any
  }): Task {
    return new Task(
      params.id,
      params.name,
      params.status,
      params.jobId.toString(),
      params.sequence,
      params.attendanceRequirement,
      params.isSetupTask,
      [],
      [],
      params.taskModes || [],
      params.createdAt,
      params.updatedAt,
    )
  }

  // Domain event methods for compatibility
  getUncommittedEvents(): any[] {
    return []
  }
  
  markEventsAsCommitted(): void {
    // Implementation would handle domain events
  }

  // Version property for optimistic concurrency
  get version(): { toNumber(): number } {
    return { toNumber: () => 1 }
  }
}