"use strict";
/**
 * Machine domain entity representing production equipment
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.MachineStatus = void 0;
var MachineStatus;
(function (MachineStatus) {
    MachineStatus["Available"] = "available";
    MachineStatus["Busy"] = "busy";
    MachineStatus["Maintenance"] = "maintenance";
    MachineStatus["Offline"] = "offline";
})(MachineStatus || (exports.MachineStatus = MachineStatus = {}));
