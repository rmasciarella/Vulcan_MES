"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Duration = exports.TaskMode = exports.TaskStatus = void 0;
var TaskStatus;
(function (TaskStatus) {
    TaskStatus["PENDING"] = "pending";
    TaskStatus["IN_PROGRESS"] = "in_progress";
    TaskStatus["COMPLETED"] = "completed";
    TaskStatus["CANCELLED"] = "cancelled";
    TaskStatus["BLOCKED"] = "blocked";
})(TaskStatus || (exports.TaskStatus = TaskStatus = {}));
var TaskMode;
(function (TaskMode) {
    TaskMode["MANUAL"] = "manual";
    TaskMode["AUTOMATIC"] = "automatic";
    TaskMode["SEMI_AUTOMATIC"] = "semi_automatic";
})(TaskMode || (exports.TaskMode = TaskMode = {}));
var Duration = /** @class */ (function () {
    function Duration(hours, minutes) {
        if (minutes === void 0) { minutes = 0; }
        this.hours = hours;
        this.minutes = minutes;
        if (hours < 0 || minutes < 0 || minutes >= 60) {
            throw new Error('Invalid duration values');
        }
    }
    Object.defineProperty(Duration.prototype, "totalMinutes", {
        get: function () {
            return this.hours * 60 + this.minutes;
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(Duration.prototype, "totalHours", {
        get: function () {
            return this.hours + this.minutes / 60;
        },
        enumerable: false,
        configurable: true
    });
    Duration.prototype.toString = function () {
        if (this.minutes === 0) {
            return "".concat(this.hours, "h");
        }
        return "".concat(this.hours, "h ").concat(this.minutes, "m");
    };
    Duration.fromMinutes = function (minutes) {
        var hours = Math.floor(minutes / 60);
        var remainingMinutes = minutes % 60;
        return new Duration(hours, remainingMinutes);
    };
    Duration.fromHours = function (hours) {
        var wholeHours = Math.floor(hours);
        var minutes = Math.round((hours - wholeHours) * 60);
        return new Duration(wholeHours, minutes);
    };
    return Duration;
}());
exports.Duration = Duration;
