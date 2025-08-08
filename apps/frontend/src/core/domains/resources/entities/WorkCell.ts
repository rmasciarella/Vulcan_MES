// Temporary WorkCell entity to fix TypeScript compilation errors

export class WorkCellId {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): WorkCellId {
    return new WorkCellId(value)
  }
}

export class WorkCellName {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): WorkCellName {
    return new WorkCellName(value)
  }
}

export class WorkCell {
  constructor(
    public id: WorkCellId,
    public name: WorkCellName,
    public description: string,
  ) {}
  
  static create(params: {
    id: string
    name: string
    description: string
  }): WorkCell {
    return new WorkCell(
      WorkCellId.create(params.id),
      WorkCellName.create(params.name),
      params.description,
    )
  }
}