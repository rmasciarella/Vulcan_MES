export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      operators: {
        Row: {
          operator_id: string
          first_name: string
          last_name: string
          employee_id: string
          department_id?: string | null
          email?: string | null
          phone_number?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at: string
          updated_at: string
        }
        Insert: {
          operator_id?: string
          first_name: string
          last_name: string
          employee_id: string
          department_id?: string | null
          email?: string | null
          phone_number?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          operator_id?: string
          first_name?: string
          last_name?: string
          employee_id?: string
          department_id?: string | null
          email?: string | null
          phone_number?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at?: string
          updated_at?: string
        }
      }
      machines: {
        Row: {
          id: string
          name: string
          machine_type?: string | null
          work_cell_id?: string | null
          department_id?: string | null
          serial_number?: string | null
          description?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          name: string
          machine_type?: string | null
          work_cell_id?: string | null
          department_id?: string | null
          serial_number?: string | null
          description?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          name?: string
          machine_type?: string | null
          work_cell_id?: string | null
          department_id?: string | null
          serial_number?: string | null
          description?: string | null
          status?: string | null
          is_active?: boolean | null
          created_at?: string
          updated_at?: string
        }
      }
      scheduled_tasks: {
        Row: {
          id: string
          operator_id?: string | null
          machine_id?: string | null
          task_name?: string | null
          scheduled_start: string
          scheduled_end: string
          status?: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          operator_id?: string | null
          machine_id?: string | null
          task_name?: string | null
          scheduled_start: string
          scheduled_end: string
          status?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          operator_id?: string | null
          machine_id?: string | null
          task_name?: string | null
          scheduled_start?: string
          scheduled_end?: string
          status?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      job_instances: {
        Row: {
          instance_id: string
          name: string
          status: string
          created_at: string
          updated_at: string
        }
        Insert: {
          instance_id?: string
          name: string
          status?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          instance_id?: string
          name?: string
          status?: string
          created_at?: string
          updated_at?: string
        }
      }
      solved_schedules: {
        Row: {
          id: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          created_at?: string
          updated_at?: string
        }
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}