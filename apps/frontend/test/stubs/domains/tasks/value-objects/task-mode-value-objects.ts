export const TaskModeTypeValue = { PRIMARY: 'PRIMARY' } as const
export type TaskModeTypeValue = (typeof TaskModeTypeValue)[keyof typeof TaskModeTypeValue]
export class TaskModeType { constructor(public value: TaskModeTypeValue) {} }
export class TaskModeId { toString() { return 'stub' } }
export class TaskModeName { static create(n: string) { return new TaskModeName() } }
export class TaskModeDuration { static create(n: number) { return new TaskModeDuration() } }
export class TaskId { static fromString(n: string) { return new TaskId() } toString(){return 'stub'} }
export class SkillLevel {}
export class WorkCellId {}
