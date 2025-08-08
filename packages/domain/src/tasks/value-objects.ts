export enum TaskStatus {
  NOT_READY = 'not_ready',
  READY = 'ready',
  PENDING = 'pending', 
  SCHEDULED = 'scheduled',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  ON_HOLD = 'on_hold',
  CANCELLED = 'cancelled',
  BLOCKED = 'blocked'
}

// Export as TaskStatusValue for compatibility with frontend
export const TaskStatusValue = TaskStatus;

export enum TaskMode {
  MANUAL = 'manual',
  AUTOMATIC = 'automatic',
  SEMI_AUTOMATIC = 'semi_automatic'
}

export class Duration {
  constructor(
    public readonly hours: number,
    public readonly minutes: number = 0
  ) {
    if (hours < 0 || minutes < 0 || minutes >= 60) {
      throw new Error('Invalid duration values');
    }
  }

  get totalMinutes(): number {
    return this.hours * 60 + this.minutes;
  }

  get totalHours(): number {
    return this.hours + this.minutes / 60;
  }

  toString(): string {
    if (this.minutes === 0) {
      return `${this.hours}h`;
    }
    return `${this.hours}h ${this.minutes}m`;
  }

  static fromMinutes(minutes: number): Duration {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return new Duration(hours, remainingMinutes);
  }

  static fromHours(hours: number): Duration {
    const wholeHours = Math.floor(hours);
    const minutes = Math.round((hours - wholeHours) * 60);
    return new Duration(wholeHours, minutes);
  }
}

// Task sequence value object
export class TaskSequence {
  constructor(private _value: number) {
    if (_value < 0) {
      throw new Error('Task sequence must be non-negative');
    }
  }
  
  get value(): number {
    return this._value;
  }
  
  static create(value: number): TaskSequence {
    return new TaskSequence(value);
  }
  
  equals(other: TaskSequence): boolean {
    return this._value === other._value;
  }
  
  toString(): string {
    return this._value.toString();
  }
}

// Attendance requirement value object
export class AttendanceRequirement {
  constructor(private _isUnattended: boolean) {}
  
  get isUnattended(): boolean {
    return this._isUnattended;
  }
  
  get isAttended(): boolean {
    return !this._isUnattended;
  }
  
  static create(isUnattended: boolean): AttendanceRequirement {
    return new AttendanceRequirement(isUnattended);
  }
  
  static createAttended(): AttendanceRequirement {
    return new AttendanceRequirement(false);
  }
  
  static createUnattended(): AttendanceRequirement {
    return new AttendanceRequirement(true);
  }
  
  equals(other: AttendanceRequirement): boolean {
    return this._isUnattended === other._isUnattended;
  }
  
  toString(): string {
    return this._isUnattended ? 'Unattended' : 'Attended';
  }
}

// Task ID value object
export class TaskId {
  constructor(private value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('TaskId cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: TaskId): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): TaskId {
    return new TaskId(value);
  }
}

// Task name value object
export class TaskName {
  constructor(private value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('TaskName cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: TaskName): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): TaskName {
    return new TaskName(value);
  }
}