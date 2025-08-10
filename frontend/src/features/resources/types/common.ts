// Common resource types and value objects

export class ResourceId {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): ResourceId {
    return new ResourceId(value)
  }
}

export class ResourceName {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): ResourceName {
    return new ResourceName(value)
  }
}

export class ResourceCapacity {
  constructor(private value: number) {}
  
  getValue(): number {
    return this.value
  }
  
  static create(value: number): ResourceCapacity {
    return new ResourceCapacity(value)
  }
}

// Common resource status
export enum ResourceStatus {
  AVAILABLE = 'available',
  IN_USE = 'in_use',
  MAINTENANCE = 'maintenance',
  OFFLINE = 'offline'
}