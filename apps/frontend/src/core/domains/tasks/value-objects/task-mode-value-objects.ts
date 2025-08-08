// Task mode value objects

export class TaskModeCode {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskModeCode {
    return new TaskModeCode(value)
  }
}

export class TaskModeDescription {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): TaskModeDescription {
    return new TaskModeDescription(value)
  }
}