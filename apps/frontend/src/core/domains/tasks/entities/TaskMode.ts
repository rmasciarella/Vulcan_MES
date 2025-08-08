// Temporary TaskMode entity to fix TypeScript compilation errors

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