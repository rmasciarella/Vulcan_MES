import { Database } from '../../../types/supabase'

// Type aliases for better readability
export type Tables = Database['public']['Tables']
export type Enums = Database['public']['Enums']

// Specific table type exports for hooks and components
export type Machine = Tables['machines']['Row']
export type MachineInsert = Tables['machines']['Insert']
export type MachineUpdate = Tables['machines']['Update']

export type Operator = Tables['operators']['Row']
export type OperatorInsert = Tables['operators']['Insert']
export type OperatorUpdate = Tables['operators']['Update']

export type SolvedSchedule = Tables['solved_schedules']['Row']
export type SolvedScheduleInsert = Tables['solved_schedules']['Insert']
export type SolvedScheduleUpdate = Tables['solved_schedules']['Update']

export type ScheduledTask = Tables['scheduled_tasks']['Row']
export type ScheduledTaskInsert = Tables['scheduled_tasks']['Insert']
export type ScheduledTaskUpdate = Tables['scheduled_tasks']['Update']

export type JobInstance = Tables['job_instances']['Row']
export type JobInstanceInsert = Tables['job_instances']['Insert']
export type JobInstanceUpdate = Tables['job_instances']['Update']

// Task type alias for consistency (maps to scheduled_tasks)
export type Task = Tables['scheduled_tasks']['Row']
export type TaskInsert = Tables['scheduled_tasks']['Insert']
export type TaskUpdate = Tables['scheduled_tasks']['Update']
