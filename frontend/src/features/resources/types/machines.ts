// Machine domain types for resources feature

export class MachineId {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): MachineId {
    return new MachineId(value)
  }
}

export class MachineName {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): MachineName {
    return new MachineName(value)
  }
}

export class Machine {
  constructor(
    public id: MachineId,
    public name: MachineName,
    public description: string,
  ) {}
  
  static create(params: {
    id: string
    name: string
    description: string
  }): Machine {
    return new Machine(
      MachineId.create(params.id),
      MachineName.create(params.name),
      params.description,
    )
  }
}