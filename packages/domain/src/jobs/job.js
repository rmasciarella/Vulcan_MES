"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.JobEntity = void 0;
var value_objects_1 = require("./value-objects");
var JobEntity = /** @class */ (function () {
    function JobEntity(id, serialNumber, productType, status, priority, dueDate, releaseDate, templateId, createdAt, updatedAt) {
        this.id = id;
        this.serialNumber = serialNumber;
        this.productType = productType;
        this.status = status;
        this.priority = priority;
        this.dueDate = dueDate;
        this.releaseDate = releaseDate;
        this.templateId = templateId;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }
    JobEntity.create = function (params) {
        var now = new Date();
        return new JobEntity(value_objects_1.JobId.create(params.id), value_objects_1.SerialNumber.create(params.serialNumber), value_objects_1.ProductType.create(params.productType), value_objects_1.JobStatus.DRAFT, params.priority, params.dueDate ? value_objects_1.DueDate.create(params.dueDate) : null, params.releaseDate ? value_objects_1.ReleaseDate.create(params.releaseDate) : null, params.templateId, now, now);
    };
    JobEntity.prototype.updateStatus = function (newStatus) {
        this.status = newStatus;
        this.updatedAt = new Date();
    };
    return JobEntity;
}());
exports.JobEntity = JobEntity;
