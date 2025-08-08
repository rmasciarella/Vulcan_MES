// Job value objects exports

export type { Job, Task as JobTask } from '../jobs'
export { 
  JobStatusValue, 
  JobStatus, 
  JobId, 
  SerialNumber, 
  ProductType, 
  DueDate, 
  ReleaseDate
} from '../jobs'

// Additional value objects for jobs
export class JobPriority {
  constructor(private value: number) {}
  
  getValue(): number {
    return this.value
  }
  
  static create(value: number): JobPriority {
    return new JobPriority(value)
  }
}

export class JobDescription {
  constructor(private value: string) {}
  
  toString(): string {
    return this.value
  }
  
  static create(value: string): JobDescription {
    return new JobDescription(value)
  }
}