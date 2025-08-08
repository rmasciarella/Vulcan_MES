// Temporary simplified domain types for frontend compilation
// TODO: Replace with proper domain package imports once ESM issues are resolved

export enum JobStatusValue {
  DRAFT = 'DRAFT',
  SCHEDULED = 'SCHEDULED',
  IN_PROGRESS = 'IN_PROGRESS',
  ON_HOLD = 'ON_HOLD',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED'
}

export enum JobPriority {
  LOW = 'low',
  MEDIUM = 'medium', 
  HIGH = 'high',
  CRITICAL = 'critical'
}

// Simple value objects for frontend compatibility
export class JobId {
  constructor(private value: string) {}
  toString(): string { return this.value }
  static create(value: string): JobId { return new JobId(value) }
}

export class SerialNumber {
  constructor(private value: string) {}
  toString(): string { return this.value }
  static create(value: string): SerialNumber { return new SerialNumber(value) }
}

export class ProductType {
  constructor(private value: string) {}
  toString(): string { return this.value }
  static create(value: string): ProductType { return new ProductType(value) }
}

export class DueDate {
  constructor(private value: Date) {}
  toDate(): Date { return this.value }
  static create(value: Date): DueDate { return new DueDate(value) }
}

export class ReleaseDate {
  constructor(private value: Date) {}
  toDate(): Date { return this.value }
  static create(value: Date): ReleaseDate { return new ReleaseDate(value) }
}

export class JobStatus {
  constructor(private _value: JobStatusValue) {}
  
  getValue(): JobStatusValue {
    return this._value;
  }
  
  toString(): string {
    return this._value;
  }
  
  static create(value: JobStatusValue): JobStatus {
    return new JobStatus(value);
  }
  
  static readonly DRAFT = JobStatusValue.DRAFT;
  static readonly SCHEDULED = JobStatusValue.SCHEDULED;
  static readonly IN_PROGRESS = JobStatusValue.IN_PROGRESS;
  static readonly ON_HOLD = JobStatusValue.ON_HOLD;
  static readonly COMPLETED = JobStatusValue.COMPLETED;
  static readonly CANCELLED = JobStatusValue.CANCELLED;
}

// Job interface that matches domain expectations
export interface Job {
  id: JobId;
  serialNumber: SerialNumber;
  productType: ProductType;
  status: JobStatus;
  priority: JobPriority;
  dueDate: DueDate | null;
  releaseDate: ReleaseDate | null;
  templateId: string;
  createdAt?: Date;
  updatedAt?: Date;
}

// Job entity with factory method
export class JobEntity implements Job {
  constructor(
    public id: JobId,
    public serialNumber: SerialNumber,
    public productType: ProductType,
    public status: JobStatus,
    public priority: JobPriority,
    public dueDate: DueDate | null,
    public releaseDate: ReleaseDate | null,
    public templateId: string,
    public createdAt: Date = new Date(),
    public updatedAt: Date = new Date()
  ) {}
  
  static create(params: {
    id: string;
    serialNumber: string;
    productType: string;
    priority: JobPriority;
    templateId: string;
    dueDate?: Date | null;
    releaseDate?: Date | null;
  }): JobEntity {
    return new JobEntity(
      JobId.create(params.id),
      SerialNumber.create(params.serialNumber),
      ProductType.create(params.productType),
      JobStatus.create(JobStatusValue.DRAFT),
      params.priority,
      params.dueDate ? DueDate.create(params.dueDate) : null,
      params.releaseDate ? ReleaseDate.create(params.releaseDate) : null,
      params.templateId
    );
  }
}

// Frontend-specific Task type (temporary)
export interface Task {
  id: string;
  jobId: string;
  name: string;
  status: string;
  duration: number;
  sequence: number;
  attendanceRequirement: number;
  isSetupTask: boolean;
  assignedTo?: string;
  mode?: TaskMode;
  taskModes?: TaskMode[];
  
  // Methods
  areTaskModesLoaded(): boolean;
  getPrimaryMode(): TaskMode | undefined;
  hasMultipleModes(): boolean;
}

// Task Mode interface
export interface TaskMode {
  id: string;
  name: string;
  skills?: string[];
  workcenters?: string[];
}