import { JobStatus, JobPriority, JobId, JobName, SerialNumber, ProductType, DueDate, ReleaseDate } from './value-objects';

// Simple task interface for job aggregation
export interface TaskSummary {
  id: string;
  jobId: string;
  name: string;
  status: string;
  sequence?: number;
}

export interface Job {
  id: JobId;
  name: JobName;
  serialNumber: SerialNumber;
  productType: ProductType;
  status: JobStatus;
  priority: JobPriority;
  dueDate: DueDate | null;
  releaseDate: ReleaseDate | null;
  templateId: string;
  tasks: TaskSummary[];
  createdAt: Date;
  updatedAt: Date;
}

export class JobEntity implements Job {
  constructor(
    public id: JobId,
    public name: JobName,
    public serialNumber: SerialNumber,
    public productType: ProductType,
    public status: JobStatus,
    public priority: JobPriority,
    public dueDate: DueDate | null,
    public releaseDate: ReleaseDate | null,
    public templateId: string,
    public tasks: TaskSummary[] = [],
    public createdAt: Date,
    public updatedAt: Date
  ) {}

  static create(params: {
    id: string;
    name: string;
    serialNumber: string;
    productType: string;
    priority: JobPriority;
    templateId: string;
    dueDate?: Date | null;
    releaseDate?: Date | null;
    tasks?: TaskSummary[];
  }): JobEntity {
    const now = new Date();
    return new JobEntity(
      JobId.create(params.id),
      JobName.create(params.name),
      SerialNumber.create(params.serialNumber),
      ProductType.create(params.productType),
      JobStatus.DRAFT,
      params.priority,
      params.dueDate ? DueDate.create(params.dueDate) : null,
      params.releaseDate ? ReleaseDate.create(params.releaseDate) : null,
      params.templateId,
      params.tasks || [],
      now,
      now
    );
  }

  updateStatus(newStatus: JobStatus): void {
    this.status = newStatus;
    this.updatedAt = new Date();
  }
  
  addTask(task: TaskSummary): void {
    this.tasks.push(task);
    this.updatedAt = new Date();
  }
  
  removeTask(taskId: string): void {
    this.tasks = this.tasks.filter(task => task.id !== taskId);
    this.updatedAt = new Date();
  }
}
