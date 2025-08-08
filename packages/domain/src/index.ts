// Domain boundaries (DDD) - Public API
// Expose each domain via a namespace to keep internals private
export * as Scheduling from './scheduling';
export * as WorkOrders from './work-orders';
export * as Resources from './resources';
export * as Calendars from './calendars';
export * as Skills from './skills';
export * as WorkCells from './work-cells';
export * as Jobs from './jobs';
export * as Tasks from './tasks';

// Cross-cutting domain interfaces
export * as Repositories from './repositories';
export * as UseCases from './use-cases/interfaces';

// Testing utilities (factories/builders) - intentionally exposed for test code
export * as Testing from './testing';
