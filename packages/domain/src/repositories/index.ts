/**
 * Repository interfaces for domain entities
 * Defines abstract data access patterns following the Repository pattern
 */

import { Job } from '../jobs/job';
import { Task } from '../tasks/task';
import { Machine } from '../resources/machine';
import { Operator } from '../resources/operator';
import { Schedule } from '../scheduling/schedule';

/**
 * Base repository interface with common CRUD operations
 */
export interface BaseRepository<T, TCreate, TUpdate> {
  findById(id: string): Promise<T | null>;
  findAll(filters?: Record<string, any>): Promise<T[]>;
  create(data: TCreate): Promise<T>;
  update(id: string, data: TUpdate): Promise<T>;
  delete(id: string): Promise<void>;
  exists(id: string): Promise<boolean>;
}

/**
 * Job repository interface
 */
export interface JobRepository extends BaseRepository<Job, any, any> {
  findByStatus(status: string): Promise<Job[]>;
  findByPriority(priority: string): Promise<Job[]>;
  findByDateRange(startDate: Date, endDate: Date): Promise<Job[]>;
}

/**
 * Task repository interface
 */
export interface TaskRepository extends BaseRepository<Task, any, any> {
  findByJobId(jobId: string): Promise<Task[]>;
  findByAssignee(assigneeId: string): Promise<Task[]>;
  findByStatus(status: string): Promise<Task[]>;
  findOverdueTasks(): Promise<Task[]>;
  findTasksInDateRange(startDate: Date, endDate: Date): Promise<Task[]>;
}

/**
 * Machine repository interface
 */
export interface MachineRepository extends BaseRepository<Machine, any, any> {
  findByStatus(status: string): Promise<Machine[]>;
  findByProductionZone(zoneId: string): Promise<Machine[]>;
  findByCapability(operationType: string): Promise<Machine[]>;
  findAvailableMachines(startTime: Date, endTime: Date): Promise<Machine[]>;
  findMachinesInMaintenance(): Promise<Machine[]>;
}

/**
 * Operator repository interface
 */
export interface OperatorRepository extends BaseRepository<Operator, any, any> {
  findByStatus(status: string): Promise<Operator[]>;
  findBySkill(skillName: string): Promise<Operator[]>;
  findByProductionZone(zoneId: string): Promise<Operator[]>;
  findAvailableOperators(startTime: Date, endTime: Date): Promise<Operator[]>;
  findByShift(shiftId: string): Promise<Operator[]>;
}

/**
 * Schedule repository interface
 */
export interface ScheduleRepository extends BaseRepository<Schedule, any, any> {
  findByStatus(status: string): Promise<Schedule[]>;
  findByDateRange(startDate: Date, endDate: Date): Promise<Schedule[]>;
  findActiveSchedules(): Promise<Schedule[]>;
  findSchedulesByCreator(createdBy: string): Promise<Schedule[]>;
  findSchedulesContainingJob(jobId: string): Promise<Schedule[]>;
}

/**
 * Unit of Work interface for transactional operations
 */
export interface UnitOfWork {
  jobRepository: JobRepository;
  taskRepository: TaskRepository;
  machineRepository: MachineRepository;
  operatorRepository: OperatorRepository;
  scheduleRepository: ScheduleRepository;
  
  begin(): Promise<void>;
  commit(): Promise<void>;
  rollback(): Promise<void>;
}