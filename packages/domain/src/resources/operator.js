"use strict";
/**
 * Operator domain entity representing human resources
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.OperatorStatus = void 0;
var OperatorStatus;
(function (OperatorStatus) {
    OperatorStatus["Available"] = "available";
    OperatorStatus["Busy"] = "busy";
    OperatorStatus["OnBreak"] = "on_break";
    OperatorStatus["Offline"] = "offline";
    OperatorStatus["Training"] = "training";
})(OperatorStatus || (exports.OperatorStatus = OperatorStatus = {}));
