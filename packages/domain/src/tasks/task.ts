import { TaskStatus, TaskMode, Duration, TaskSequence, AttendanceRequirement, TaskId, TaskName } from './value-objects';

export interface Task {
  id: string;
  jobId: string;
  name: string;
  status: TaskStatus;
  assignedTo?: string | undefined;
  duration: Duration;
  mode?: TaskMode;
  sequence: number;
  attendanceRequirement: number; // 0 for attended, 1 for unattended
  isSetupTask: boolean;
  taskModes?: any[]; // Array of task modes/execution options
  createdAt: Date;
  updatedAt: Date;
}

export class TaskEntity implements Task {
  constructor(
    public id: string,
    public jobId: string,
    public name: string,
    public status: TaskStatus,
    public duration: Duration,
    public sequence: number,
    public attendanceRequirement: number,
    public isSetupTask: boolean,
    public createdAt: Date,
    public updatedAt: Date,
    public assignedTo?: string,
    public mode: TaskMode = TaskMode.MANUAL,
    public taskModes: any[] = []
  ) {}

  static create(params: {
    id: string;
    jobId: string;
    name: string;
    duration: Duration;
    sequence: number;
    attendanceRequirement: number;
    isSetupTask: boolean;
    assignedTo?: string;
    mode?: TaskMode;
    taskModes?: any[];
  }): TaskEntity {
    const now = new Date();
    return new TaskEntity(
      params.id,
      params.jobId,
      params.name,
      TaskStatus.PENDING,
      params.duration,
      params.sequence,
      params.attendanceRequirement,
      params.isSetupTask,
      now,
      now,
      params.assignedTo,
      params.mode || TaskMode.MANUAL,
      params.taskModes || []
    );
  }

  updateStatus(newStatus: TaskStatus): void {
    this.status = newStatus;
    this.updatedAt = new Date();
  }

  assignTo(assigneeId: string): void {
    this.assignedTo = assigneeId;
    this.updatedAt = new Date();
  }

  updateDuration(newDuration: Duration): void {
    this.duration = newDuration;
    this.updatedAt = new Date();
  }

  updateSequence(newSequence: number): void {
    this.sequence = newSequence;
    this.updatedAt = new Date();
  }

  updateAttendanceRequirement(newRequirement: number): void {
    this.attendanceRequirement = newRequirement;
    this.updatedAt = new Date();
  }

  setAsSetupTask(isSetup: boolean): void {
    this.isSetupTask = isSetup;
    this.updatedAt = new Date();
  }

  updateTaskModes(modes: any[]): void {
    this.taskModes = modes;
    this.updatedAt = new Date();
  }

  // Helper methods for task modes
  areTaskModesLoaded(): boolean {
    return this.taskModes && this.taskModes.length > 0;
  }

  getPrimaryMode(): any | null {
    if (!this.taskModes || this.taskModes.length === 0) return null;
    return this.taskModes.find(mode => mode.isPrimary) || this.taskModes[0];
  }

  hasMultipleModes(): boolean {
    return this.taskModes ? this.taskModes.length > 1 : false;
  }

  // Helper methods for attendance
  get isUnattended(): boolean {
    return this.attendanceRequirement === 1;
  }

  get isAttended(): boolean {
    return this.attendanceRequirement === 0;
  }
}