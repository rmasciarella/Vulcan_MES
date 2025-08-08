"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createMockWorkOrder = createMockWorkOrder;
exports.createMockResource = createMockResource;
var __1 = require("..");
var __2 = require("..");
// Factory: createMockWorkOrder
function createMockWorkOrder(overrides) {
    var _a, _b, _c, _d, _e;
    if (overrides === void 0) { overrides = {}; }
    return __1.Jobs.JobEntity.create({
        id: (_a = overrides.id) !== null && _a !== void 0 ? _a : 'job-mock-001',
        serialNumber: (_b = overrides.serialNumber) !== null && _b !== void 0 ? _b : 'SN-MOCK-001',
        productType: (_c = overrides.productType) !== null && _c !== void 0 ? _c : 'Mock Product Type',
        priority: (_d = overrides.priority) !== null && _d !== void 0 ? _d : __1.Jobs.JobPriority.MEDIUM,
        templateId: (_e = overrides.templateId) !== null && _e !== void 0 ? _e : 'template-mock-001',
        dueDate: overrides.dueDate,
        releaseDate: overrides.releaseDate,
    });
}
// Factory: createMockResource (Machine by default)
function createMockResource(overrides) {
    var _a, _b, _c, _d, _e, _f, _g;
    if (overrides === void 0) { overrides = {}; }
    var now = new Date();
    return {
        id: (_a = overrides.id) !== null && _a !== void 0 ? _a : 'machine-mock-001',
        name: (_b = overrides.name) !== null && _b !== void 0 ? _b : 'Mock Machine',
        status: (_c = overrides.status) !== null && _c !== void 0 ? _c : __2.Resources.MachineStatus.Available,
        capabilities: (_d = overrides.capabilities) !== null && _d !== void 0 ? _d : [
            { operationType: 'CNC', skillsRequired: ['machining'], cycleTime: 15 },
        ],
        productionZoneId: (_e = overrides.productionZoneId) !== null && _e !== void 0 ? _e : 'zone-1',
        maintenanceWindowStart: overrides.maintenanceWindowStart,
        maintenanceWindowEnd: overrides.maintenanceWindowEnd,
        createdAt: (_f = overrides.createdAt) !== null && _f !== void 0 ? _f : now,
        updatedAt: (_g = overrides.updatedAt) !== null && _g !== void 0 ? _g : now,
    };
}
