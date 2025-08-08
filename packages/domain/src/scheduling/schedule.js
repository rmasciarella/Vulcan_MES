"use strict";
/**
 * Schedule domain entity representing production schedules
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.OptimizationObjective = exports.ScheduledTaskStatus = exports.ScheduleStatus = void 0;
var ScheduleStatus;
(function (ScheduleStatus) {
    ScheduleStatus["Draft"] = "draft";
    ScheduleStatus["Active"] = "active";
    ScheduleStatus["Completed"] = "completed";
    ScheduleStatus["Cancelled"] = "cancelled";
    ScheduleStatus["Paused"] = "paused";
})(ScheduleStatus || (exports.ScheduleStatus = ScheduleStatus = {}));
var ScheduledTaskStatus;
(function (ScheduledTaskStatus) {
    ScheduledTaskStatus["Scheduled"] = "scheduled";
    ScheduledTaskStatus["InProgress"] = "in_progress";
    ScheduledTaskStatus["Completed"] = "completed";
    ScheduledTaskStatus["Delayed"] = "delayed";
    ScheduledTaskStatus["Cancelled"] = "cancelled";
})(ScheduledTaskStatus || (exports.ScheduledTaskStatus = ScheduledTaskStatus = {}));
var OptimizationObjective;
(function (OptimizationObjective) {
    OptimizationObjective["MinimizeMakespan"] = "minimize_makespan";
    OptimizationObjective["MaximizeUtilization"] = "maximize_utilization";
    OptimizationObjective["MinimizeLateness"] = "minimize_lateness";
    OptimizationObjective["BalanceWorkload"] = "balance_workload";
})(OptimizationObjective || (exports.OptimizationObjective = OptimizationObjective = {}));
