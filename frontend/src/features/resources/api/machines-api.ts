// Simple HTTP utilities (replaced deprecated http-client import)
class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'HttpError'
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return String(error)
}

// Simple HTTP client replacement
const httpClient = {
  async get<T>(path: string): Promise<T> {
    const response = await fetch(path)
    if (!response.ok) throw new HttpError(response.status, `GET ${path} failed: ${response.status}`)
    return response.json()
  },
  async post<T>(path: string, data?: any): Promise<T> {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : null,
    })
    if (!response.ok) throw new HttpError(response.status, `POST ${path} failed: ${response.status}`)
    return response.json()
  },
  async patch<T>(path: string, data?: any): Promise<T> {
    const response = await fetch(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : null,
    })
    if (!response.ok) throw new HttpError(response.status, `PATCH ${path} failed: ${response.status}`)
    return response.json()
  },
  async delete(path: string): Promise<void> {
    const response = await fetch(path, { method: 'DELETE' })
    if (!response.ok) throw new HttpError(response.status, `DELETE ${path} failed: ${response.status}`)
  }
}
import { getSupabaseBrowserClient } from '@/infrastructure/supabase/browser-singleton'
import type { Machine, MachineInsert, MachineUpdate } from '@/core/types/database'
import { env } from '@/shared/lib/env'

/**
 * Machine availability data structure
 */
export interface MachineAvailability {
  id: string
  start: Date
  end: Date
  available: boolean
  reason?: string
}

/**
 * Machine statistics response
 */
export interface MachineStats {
  count: number
  active: number
  available: number
  utilization?: number
}

/**
 * Machine list filters
 */
export interface MachinesListFilters {
  status?: string
  type?: string
  workCellId?: string
  departmentId?: string
  isActive?: boolean
}

/**
 * Machine API client with dual-mode support (Supabase + Backend)
 * Uses Supabase as primary data source, with future backend API fallback
 */
export class MachinesAPI {
  private useBackendAPI: boolean
  private supabase = getSupabaseBrowserClient()

  constructor() {
    // Use backend API if configured, otherwise fallback to Supabase
    this.useBackendAPI = !!env.NEXT_PUBLIC_API_URL
  }

  /**
   * Fetch machines list with optional filtering
   */
  async getMachines(filters?: MachinesListFilters): Promise<Machine[]> {
    if (this.useBackendAPI) {
      return this.getMachinesFromBackend(filters)
    }
    return this.getMachinesFromSupabase(filters)
  }

  /**
   * Fetch machines from backend API
   */
  private async getMachinesFromBackend(filters?: MachinesListFilters): Promise<Machine[]> {
    try {
      const queryParams = new URLSearchParams()
      if (filters?.status) queryParams.set('status', filters.status)
      if (filters?.type) queryParams.set('type', filters.type)
      if (filters?.workCellId) queryParams.set('work_cell_id', filters.workCellId)
      if (filters?.departmentId) queryParams.set('department_id', filters.departmentId)
      if (filters?.isActive !== undefined) queryParams.set('is_active', filters.isActive.toString())

      const queryString = queryParams.toString()
      const path = `/api/v1/resources/machines${queryString ? `?${queryString}` : ''}`
      
      return await httpClient.get<Machine[]>(path)
    } catch (error) {
      throw new Error(`Failed to fetch machines from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch machines from Supabase
   */
  private async getMachinesFromSupabase(filters?: MachinesListFilters): Promise<Machine[]> {
    try {
      let query = this.supabase
        .from('machines')
        .select('*')
        .order('created_at', { ascending: false })

      // Apply filters
      if (filters?.status) {
        query = query.eq('status', filters.status)
      }
      if (filters?.type) {
        query = query.eq('machine_type', filters.type)
      }
      if (filters?.workCellId) {
        query = query.eq('work_cell_id', filters.workCellId)
      }
      if (filters?.departmentId) {
        query = query.eq('department_id', filters.departmentId)
      }
      if (filters?.isActive !== undefined) {
        query = query.eq('is_active', filters.isActive)
      }

      const { data, error } = await query

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Machine[]
    } catch (error) {
      throw new Error(`Failed to fetch machines from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch single machine by ID
   */
  async getMachine(id: string): Promise<Machine> {
    if (this.useBackendAPI) {
      return this.getMachineFromBackend(id)
    }
    return this.getMachineFromSupabase(id)
  }

  /**
   * Fetch machine from backend API
   */
  private async getMachineFromBackend(id: string): Promise<Machine> {
    try {
      return await httpClient.get<Machine>(`/api/v1/resources/machines/${id}`)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Machine with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch machine from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch machine from Supabase
   */
  private async getMachineFromSupabase(id: string): Promise<Machine> {
    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          throw new Error(`Machine with ID ${id} not found`)
        }
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Machine
    } catch (error) {
      throw new Error(`Failed to fetch machine from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Create new machine
   */
  async createMachine(machineData: MachineInsert): Promise<Machine> {
    if (this.useBackendAPI) {
      return this.createMachineInBackend(machineData)
    }
    return this.createMachineInSupabase(machineData)
  }

  /**
   * Create machine via backend API
   */
  private async createMachineInBackend(machineData: MachineInsert): Promise<Machine> {
    try {
      return await httpClient.post<Machine>('/api/v1/resources/machines', machineData)
    } catch (error) {
      throw new Error(`Failed to create machine in backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Create machine in Supabase
   */
  private async createMachineInSupabase(machineData: MachineInsert): Promise<Machine> {
    try {
      const { data, error } = await this.supabase
        .from('machines')
        .insert(machineData)
        .select()
        .single()

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Machine
    } catch (error) {
      throw new Error(`Failed to create machine in Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Update machine
   */
  async updateMachine(id: string, updateData: MachineUpdate): Promise<Machine> {
    if (this.useBackendAPI) {
      return this.updateMachineInBackend(id, updateData)
    }
    return this.updateMachineInSupabase(id, updateData)
  }

  /**
   * Update machine via backend API
   */
  private async updateMachineInBackend(id: string, updateData: MachineUpdate): Promise<Machine> {
    try {
      return await httpClient.patch<Machine>(`/api/v1/resources/machines/${id}`, updateData)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Machine with ID ${id} not found`)
      }
      throw new Error(`Failed to update machine in backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Update machine in Supabase
   */
  private async updateMachineInSupabase(id: string, updateData: MachineUpdate): Promise<Machine> {
    try {
      const updates = {
        ...updateData,
        updated_at: new Date().toISOString(),
      }

      const { data, error } = await this.supabase
        .from('machines')
        .update(updates)
        .eq('id', id)
        .select()
        .single()

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Machine
    } catch (error) {
      throw new Error(`Failed to update machine in Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Delete machine
   */
  async deleteMachine(id: string): Promise<void> {
    if (this.useBackendAPI) {
      return this.deleteMachineFromBackend(id)
    }
    return this.deleteMachineFromSupabase(id)
  }

  /**
   * Delete machine via backend API
   */
  private async deleteMachineFromBackend(id: string): Promise<void> {
    try {
      await httpClient.delete(`/api/v1/resources/machines/${id}`)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Machine with ID ${id} not found`)
      }
      throw new Error(`Failed to delete machine from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Delete machine from Supabase
   */
  private async deleteMachineFromSupabase(id: string): Promise<void> {
    try {
      const { error } = await this.supabase
        .from('machines')
        .delete()
        .eq('id', id)

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }
    } catch (error) {
      throw new Error(`Failed to delete machine from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Get machine availability for scheduling
   */
  async getMachineAvailability(
    id: string, 
    start: Date, 
    end: Date
  ): Promise<MachineAvailability[]> {
    if (this.useBackendAPI) {
      try {
        const queryParams = new URLSearchParams({
          start_time: start.toISOString(),
          end_time: end.toISOString(),
        })
        
        return await httpClient.get<MachineAvailability[]>(
          `/api/v1/resources/machines/${id}/availability?${queryParams}`
        )
      } catch (error) {
        throw new Error(`Failed to fetch machine availability from backend: ${getErrorMessage(error)}`)
      }
    }

    // Supabase fallback - simplified availability check
    try {
      const machine = await this.getMachineFromSupabase(id)
      
      // Simple availability based on machine status and active state
      const isAvailable = Boolean(machine.is_active && machine.status === 'operational')
      
      const reasonText = !isAvailable ? `Machine is ${machine.status}` : undefined
      
      return [{
        id,
        start,
        end,
        available: isAvailable,
        ...(reasonText !== undefined && { reason: reasonText }),
      }]
    } catch (error) {
      throw new Error(`Failed to check machine availability: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Get machine statistics
   */
  async getMachineStats(): Promise<MachineStats> {
    if (this.useBackendAPI) {
      try {
        return await httpClient.get<MachineStats>('/api/v1/resources/machines/stats')
      } catch (error) {
        throw new Error(`Failed to fetch machine stats from backend: ${getErrorMessage(error)}`)
      }
    }

    // Supabase fallback
    try {
      const machines = await this.getMachinesFromSupabase()
      
      const active = machines.filter(m => m.is_active && m.status === 'operational').length
      const available = machines.filter(m => 
        m.is_active && ['operational', 'idle'].includes(m.status || '')
      ).length

      return {
        count: machines.length,
        active,
        available,
      }
    } catch (error) {
      throw new Error(`Failed to calculate machine stats: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Specialized queries for dashboard components
   */
  async getActiveMachines(): Promise<Machine[]> {
    return this.getMachines({ isActive: true })
  }

  async getAvailableMachines(): Promise<Machine[]> {
    return this.getMachines({ isActive: true, status: 'operational' })
  }

  async getMachinesByWorkCell(workCellId: string): Promise<Machine[]> {
    return this.getMachines({ workCellId })
  }

  async getMachinesByType(machineType: string): Promise<Machine[]> {
    return this.getMachines({ type: machineType })
  }
}

/**
 * Export singleton instance
 */
export const machinesAPI = new MachinesAPI()