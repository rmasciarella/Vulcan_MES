"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TaskEntity = void 0;
var value_objects_1 = require("./value-objects");
var TaskEntity = /** @class */ (function () {
    function TaskEntity(id, jobId, name, status, duration, createdAt, updatedAt, assignedTo, mode) {
        if (mode === void 0) { mode = value_objects_1.TaskMode.MANUAL; }
        this.id = id;
        this.jobId = jobId;
        this.name = name;
        this.status = status;
        this.duration = duration;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.assignedTo = assignedTo;
        this.mode = mode;
    }
    TaskEntity.create = function (params) {
        var now = new Date();
        return new TaskEntity(params.id, params.jobId, params.name, value_objects_1.TaskStatus.PENDING, params.duration, now, now, params.assignedTo, params.mode || value_objects_1.TaskMode.MANUAL);
    };
    TaskEntity.prototype.updateStatus = function (newStatus) {
        this.status = newStatus;
        this.updatedAt = new Date();
    };
    TaskEntity.prototype.assignTo = function (assigneeId) {
        this.assignedTo = assigneeId;
        this.updatedAt = new Date();
    };
    TaskEntity.prototype.updateDuration = function (newDuration) {
        this.duration = newDuration;
        this.updatedAt = new Date();
    };
    return TaskEntity;
}());
exports.TaskEntity = TaskEntity;
