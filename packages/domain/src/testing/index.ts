import { Jobs } from '..';
import { Resources } from '..';

// Factory: createMockWorkOrder
export function createMockWorkOrder(overrides: Partial<{
  id: string;
  name: string;
  serialNumber: string;
  productType: string;
  priority: Jobs.JobPriority;
  templateId: string;
  dueDate?: Date | null;
  releaseDate?: Date | null;
}> = {}) {
  return Jobs.JobEntity.create({
    id: overrides.id ?? 'job-mock-001',
    name: overrides.name ?? 'Mock Job Name',
    serialNumber: overrides.serialNumber ?? 'SN-MOCK-001',
    productType: overrides.productType ?? 'Mock Product Type',
    priority: overrides.priority ?? Jobs.JobPriority.MEDIUM,
    templateId: overrides.templateId ?? 'template-mock-001',
    dueDate: overrides.dueDate,
    releaseDate: overrides.releaseDate,
  });
}

// Factory: createMockResource (Machine by default)
export function createMockResource(overrides: Partial<Resources.Machine> = {}): Resources.Machine {
  const now = new Date();
  return {
    id: overrides.id ?? 'machine-mock-001',
    name: overrides.name ?? 'Mock Machine',
    status: overrides.status ?? Resources.MachineStatus.Available,
    capabilities: overrides.capabilities ?? [
      { operationType: 'CNC', skillsRequired: ['machining'], cycleTime: 15 },
    ],
    productionZoneId: overrides.productionZoneId ?? 'zone-1',
    maintenanceWindowStart: overrides.maintenanceWindowStart,
    maintenanceWindowEnd: overrides.maintenanceWindowEnd,
    createdAt: overrides.createdAt ?? now,
    updatedAt: overrides.updatedAt ?? now,
  };
}
