"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.Testing = exports.Repositories = exports.Tasks = exports.Jobs = exports.WorkCells = exports.Skills = exports.Calendars = exports.Resources = exports.WorkOrders = exports.Scheduling = void 0;
// Domain boundaries (DDD) - Public API
// Expose each domain via a namespace to keep internals private
exports.Scheduling = __importStar(require("./scheduling"));
exports.WorkOrders = __importStar(require("./work-orders"));
exports.Resources = __importStar(require("./resources"));
exports.Calendars = __importStar(require("./calendars"));
exports.Skills = __importStar(require("./skills"));
exports.WorkCells = __importStar(require("./work-cells"));
exports.Jobs = __importStar(require("./jobs"));
exports.Tasks = __importStar(require("./tasks"));
// Cross-cutting domain interfaces
exports.Repositories = __importStar(require("./repositories"));
// Testing utilities (factories/builders) - intentionally exposed for test code
exports.Testing = __importStar(require("./testing"));
