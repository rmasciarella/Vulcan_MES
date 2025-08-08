/**
 * Machine domain entity representing production equipment
 */

export enum MachineStatus {
  Available = 'available',
  Busy = 'busy',
  Maintenance = 'maintenance',
  Offline = 'offline'
}

export interface MachineCapability {
  operationType: string;
  skillsRequired: string[];
  cycleTime: number; // in minutes
}

export interface Machine {
  id: string;
  name: string;
  status: MachineStatus;
  capabilities: MachineCapability[];
  productionZoneId?: string;
  maintenanceWindowStart?: Date;
  maintenanceWindowEnd?: Date;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateMachineData {
  name: string;
  capabilities: MachineCapability[];
  productionZoneId?: string;
}

export interface UpdateMachineData {
  name?: string;
  status?: MachineStatus;
  capabilities?: MachineCapability[];
  productionZoneId?: string;
  maintenanceWindowStart?: Date;
  maintenanceWindowEnd?: Date;
}