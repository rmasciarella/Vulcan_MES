/**
 * Schedule domain entity representing production schedules
 */

export enum ScheduleStatus {
  Draft = 'draft',
  Active = 'active',
  Completed = 'completed',
  Cancelled = 'cancelled',
  Paused = 'paused'
}

export interface ScheduledTask {
  taskId: string;
  jobId: string;
  machineId: string;
  operatorId: string;
  startTime: Date;
  endTime: Date;
  estimatedDuration: number; // in minutes
  actualStartTime?: Date;
  actualEndTime?: Date;
  actualDuration?: number; // in minutes
  status: ScheduledTaskStatus;
}

export enum ScheduledTaskStatus {
  Scheduled = 'scheduled',
  InProgress = 'in_progress',
  Completed = 'completed',
  Delayed = 'delayed',
  Cancelled = 'cancelled'
}

export interface ScheduleMetrics {
  totalTasks: number;
  completedTasks: number;
  makespan: number; // total schedule duration in minutes
  utilization: number; // percentage of resource utilization
  onTimePerformance: number; // percentage of on-time deliveries
}

export interface Schedule {
  id: string;
  name: string;
  status: ScheduleStatus;
  tasks: ScheduledTask[];
  startDate: Date;
  endDate: Date;
  createdBy: string;
  metrics?: ScheduleMetrics;
  optimizationObjective: OptimizationObjective;
  constraints: ScheduleConstraints;
  createdAt: Date;
  updatedAt: Date;
}

export enum OptimizationObjective {
  MinimizeMakespan = 'minimize_makespan',
  MaximizeUtilization = 'maximize_utilization',
  MinimizeLateness = 'minimize_lateness',
  BalanceWorkload = 'balance_workload'
}

export interface ScheduleConstraints {
  maxWipPerZone?: number;
  respectMaintenanceWindows: boolean;
  respectOperatorAvailability: boolean;
  allowOvertime: boolean;
  maxOvertimeHoursPerDay?: number;
}

export interface CreateScheduleData {
  name: string;
  jobIds: string[];
  startDate: Date;
  endDate: Date;
  optimizationObjective: OptimizationObjective;
  constraints: ScheduleConstraints;
}

export interface UpdateScheduleData {
  name?: string;
  status?: ScheduleStatus;
  startDate?: Date;
  endDate?: Date;
  optimizationObjective?: OptimizationObjective;
  constraints?: ScheduleConstraints;
}