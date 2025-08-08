/**
 * Operator domain entity representing human resources
 */

export enum OperatorStatus {
  Available = 'available',
  Busy = 'busy',
  OnBreak = 'on_break',
  Offline = 'offline',
  Training = 'training'
}

export interface OperatorSkill {
  skillName: string;
  proficiencyLevel: number; // 1-5 scale
  certifiedAt: Date;
  expiresAt?: Date;
}

export interface OperatorAvailability {
  dayOfWeek: number; // 0-6 (Sunday-Saturday)
  startTime: string; // HH:MM format
  endTime: string; // HH:MM format
}

export interface Operator {
  id: string;
  name: string;
  email: string;
  status: OperatorStatus;
  skills: OperatorSkill[];
  availability: OperatorAvailability[];
  productionZoneId?: string;
  shiftId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateOperatorData {
  name: string;
  email: string;
  skills: OperatorSkill[];
  availability: OperatorAvailability[];
  productionZoneId?: string;
  shiftId?: string;
}

export interface UpdateOperatorData {
  name?: string;
  email?: string;
  status?: OperatorStatus;
  skills?: OperatorSkill[];
  availability?: OperatorAvailability[];
  productionZoneId?: string;
  shiftId?: string;
}