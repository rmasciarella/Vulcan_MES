"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ReleaseDate = exports.DueDate = exports.ProductType = exports.SerialNumber = exports.JobId = exports.JobPriority = exports.JobStatusValue = exports.JobStatus = void 0;
var JobStatus;
(function (JobStatus) {
    JobStatus["DRAFT"] = "DRAFT";
    JobStatus["SCHEDULED"] = "SCHEDULED";
    JobStatus["IN_PROGRESS"] = "IN_PROGRESS";
    JobStatus["ON_HOLD"] = "ON_HOLD";
    JobStatus["COMPLETED"] = "COMPLETED";
    JobStatus["CANCELLED"] = "CANCELLED";
})(JobStatus || (exports.JobStatus = JobStatus = {}));
// Frontend-compatible status enum (same as JobStatus but exported as JobStatusValue)
exports.JobStatusValue = JobStatus;
var JobPriority;
(function (JobPriority) {
    JobPriority["LOW"] = "low";
    JobPriority["MEDIUM"] = "medium";
    JobPriority["HIGH"] = "high";
    JobPriority["CRITICAL"] = "critical";
})(JobPriority || (exports.JobPriority = JobPriority = {}));
// Job-related value objects
var JobId = /** @class */ (function () {
    function JobId(value) {
        this.value = value;
        if (!value || value.trim().length === 0) {
            throw new Error('JobId cannot be empty');
        }
    }
    JobId.prototype.toString = function () {
        return this.value;
    };
    JobId.prototype.equals = function (other) {
        return this.value === other.value;
    };
    JobId.create = function (value) {
        return new JobId(value);
    };
    return JobId;
}());
exports.JobId = JobId;
var SerialNumber = /** @class */ (function () {
    function SerialNumber(value) {
        this.value = value;
        if (!value || value.trim().length === 0) {
            throw new Error('SerialNumber cannot be empty');
        }
    }
    SerialNumber.prototype.toString = function () {
        return this.value;
    };
    SerialNumber.prototype.equals = function (other) {
        return this.value === other.value;
    };
    SerialNumber.create = function (value) {
        return new SerialNumber(value);
    };
    return SerialNumber;
}());
exports.SerialNumber = SerialNumber;
var ProductType = /** @class */ (function () {
    function ProductType(value) {
        this.value = value;
        if (!value || value.trim().length === 0) {
            throw new Error('ProductType cannot be empty');
        }
    }
    ProductType.prototype.toString = function () {
        return this.value;
    };
    ProductType.prototype.equals = function (other) {
        return this.value === other.value;
    };
    ProductType.create = function (value) {
        return new ProductType(value);
    };
    return ProductType;
}());
exports.ProductType = ProductType;
var DueDate = /** @class */ (function () {
    function DueDate(value) {
        this.value = value;
        if (!value || isNaN(value.getTime())) {
            throw new Error('DueDate must be a valid date');
        }
    }
    DueDate.prototype.toDate = function () {
        return new Date(this.value.getTime());
    };
    DueDate.prototype.equals = function (other) {
        return this.value.getTime() === other.value.getTime();
    };
    DueDate.create = function (value) {
        return new DueDate(value);
    };
    return DueDate;
}());
exports.DueDate = DueDate;
var ReleaseDate = /** @class */ (function () {
    function ReleaseDate(value) {
        this.value = value;
        if (!value || isNaN(value.getTime())) {
            throw new Error('ReleaseDate must be a valid date');
        }
    }
    ReleaseDate.prototype.toDate = function () {
        return new Date(this.value.getTime());
    };
    ReleaseDate.prototype.equals = function (other) {
        return this.value.getTime() === other.value.getTime();
    };
    ReleaseDate.create = function (value) {
        return new ReleaseDate(value);
    };
    return ReleaseDate;
}());
exports.ReleaseDate = ReleaseDate;
