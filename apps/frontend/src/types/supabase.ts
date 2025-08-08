// Minimal Supabase type definitions to enable compilation
// These provide basic type safety while the full database schema is implemented

export interface Database {
  public: {
    Tables: {
      job_instances: {
        Row: JobInstance;
        Insert: Partial<JobInstance>;
        Update: Partial<JobInstance>;
      };
    };
  };
}

export interface JobInstance {
  instance_id: string;
  name: string;
  description: string | null;
  status: 'DRAFT' | 'SCHEDULED' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETED' | 'CANCELLED';
  template_id: string;
  due_date: string | null;
  earliest_start_date: string | null;
  created_at: string;
  updated_at: string;
  version?: number | null;
}

// Helper type to get table row types
export type Tables<T extends keyof Database['public']['Tables']> = 
  Database['public']['Tables'][T]['Row'];