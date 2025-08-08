export enum JobStatus {
  DRAFT = 'DRAFT',
  PENDING = 'PENDING', // Added missing status expected by tests
  SCHEDULED = 'SCHEDULED',
  IN_PROGRESS = 'IN_PROGRESS',
  ON_HOLD = 'ON_HOLD',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED'
}

// Frontend-compatible status enum (same as JobStatus but exported as JobStatusValue)
export const JobStatusValue = JobStatus;

export enum JobPriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

// Job-related value objects
export class JobId {
  constructor(private readonly value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('JobId cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: JobId): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): JobId {
    return new JobId(value);
  }
}

export class JobName {
  constructor(private readonly value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('JobName cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: JobName): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): JobName {
    return new JobName(value);
  }
}

export class SerialNumber {
  constructor(private readonly value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('SerialNumber cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: SerialNumber): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): SerialNumber {
    return new SerialNumber(value);
  }
}

export class ProductType {
  constructor(private readonly value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error('ProductType cannot be empty');
    }
  }
  
  toString(): string {
    return this.value;
  }
  
  equals(other: ProductType): boolean {
    return this.value === other.value;
  }
  
  static create(value: string): ProductType {
    return new ProductType(value);
  }
}

export class DueDate {
  constructor(private readonly value: Date) {
    if (!value || isNaN(value.getTime())) {
      throw new Error('DueDate must be a valid date');
    }
  }
  
  toDate(): Date {
    return new Date(this.value.getTime());
  }
  
  equals(other: DueDate): boolean {
    return this.value.getTime() === other.value.getTime();
  }
  
  static create(value: Date): DueDate {
    return new DueDate(value);
  }
}

export class ReleaseDate {
  constructor(private readonly value: Date) {
    if (!value || isNaN(value.getTime())) {
      throw new Error('ReleaseDate must be a valid date');
    }
  }
  
  toDate(): Date {
    return new Date(this.value.getTime());
  }
  
  equals(other: ReleaseDate): boolean {
    return this.value.getTime() === other.value.getTime();
  }
  
  static create(value: Date): ReleaseDate {
    return new ReleaseDate(value);
  }
}