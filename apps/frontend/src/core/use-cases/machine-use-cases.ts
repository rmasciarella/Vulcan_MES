import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '@/types/supabase'
import type { Machine } from '@/core/types/database'

/**
 * Filters interface for machine queries
 */
export interface MachinesListFilters {
  isActive?: boolean
  departmentId?: string
  machineType?: string
  workCellId?: string
  status?: 'available' | 'busy' | 'maintenance' | 'offline'
}

/**
 * Machine availability data structure
 */
export interface MachineAvailability {
  id: string
  scheduled_start: string
  scheduled_end: string
  task_name?: string
  status: string
}

/**
 * Business logic layer for machine operations
 * Encapsulates all machine-related use cases and domain logic
 */
export class MachineUseCases {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Fetch machines with optional filtering
   */
  async getMachines(filters?: MachinesListFilters): Promise<Machine[]> {
    let query = this.supabase
      .from('machines')
      .select('*')
      .order('name', { ascending: true })

    if (filters?.isActive !== undefined) {
      query = query.eq('is_active', filters.isActive)
    }

    if (filters?.departmentId) {
      query = query.eq('department_id', filters.departmentId)
    }

    if (filters?.machineType) {
      query = query.eq('machine_type', filters.machineType)
    }

    if (filters?.workCellId) {
      query = query.eq('work_cell_id', filters.workCellId)
    }

    if (filters?.status) {
      query = query.eq('status', filters.status)
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch machines: ${error.message}`)
    }

    return data as Machine[]
  }

  /**
   * Fetch a single machine by ID
   */
  async getMachineById(id: string): Promise<Machine> {
    const { data, error } = await this.supabase
      .from('machines')
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        throw new Error(`Machine with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch machine: ${error.message}`)
    }

    return data as Machine
  }

  /**
   * Get machine availability within a time window
   */
  async getMachineAvailability(
    id: string, 
    startTime: Date, 
    endTime: Date
  ): Promise<MachineAvailability[]> {
    const { data, error } = await this.supabase
      .from('scheduled_tasks')
      .select(`
        id,
        scheduled_start,
        scheduled_end,
        task_name,
        status
      `)
      .eq('machine_id', id)
      .gte('scheduled_start', startTime.toISOString())
      .lte('scheduled_end', endTime.toISOString())
      .order('scheduled_start', { ascending: true })

    if (error) {
      throw new Error(`Failed to fetch machine availability: ${error.message}`)
    }

    return data as MachineAvailability[]
  }

  /**
   * Update machine active status
   */
  async updateMachineActiveStatus(id: string, isActive: boolean): Promise<Machine> {
    const { data, error } = await this.supabase
      .from('machines')
      .update({ 
        is_active: isActive,
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update machine status: ${error.message}`)
    }

    return data as Machine
  }

  /**
   * Update machine status (available, busy, maintenance, offline)
   */
  async updateMachineStatus(id: string, status: Machine['status']): Promise<Machine> {
    const { data, error } = await this.supabase
      .from('machines')
      .update({ 
        status,
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update machine status: ${error.message}`)
    }

    return data as Machine
  }

  /**
   * Get machines by work cell
   */
  async getMachinesByWorkCell(workCellId: string): Promise<Machine[]> {
    return this.getMachines({ workCellId })
  }

  /**
   * Get active machines only
   */
  async getActiveMachines(): Promise<Machine[]> {
    return this.getMachines({ isActive: true })
  }

  /**
   * Get available machines (active and status = available)
   */
  async getAvailableMachines(): Promise<Machine[]> {
    return this.getMachines({ isActive: true, status: 'available' })
  }

  /**
   * Get machines by type
   */
  async getMachinesByType(machineType: string): Promise<Machine[]> {
    return this.getMachines({ machineType })
  }

  /**
   * Create a new machine
   */
  async createMachine(machineData: {
    name: string
    machineType: string
    workCellId?: string
    departmentId?: string
    serialNumber?: string
    description?: string
  }): Promise<Machine> {
    const { data, error } = await this.supabase
      .from('machines')
      .insert({
        name: machineData.name,
        machine_type: machineData.machineType,
        work_cell_id: machineData.workCellId,
        department_id: machineData.departmentId,
        serial_number: machineData.serialNumber,
        description: machineData.description,
        status: 'available',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to create machine: ${error.message}`)
    }

    return data as Machine
  }

  /**
   * Delete a machine
   */
  async deleteMachine(id: string): Promise<void> {
    const { error } = await this.supabase
      .from('machines')
      .delete()
      .eq('id', id)

    if (error) {
      throw new Error(`Failed to delete machine: ${error.message}`)
    }
  }

  /**
   * Get machine count for analytics/statistics
   */
  async getMachineCount(): Promise<{ 
    total: number
    active: number
    available: number
    busy: number
    maintenance: number
    offline: number
  }> {
    // Get total count
    const { count: total, error: totalError } = await this.supabase
      .from('machines')
      .select('*', { count: 'exact', head: true })

    if (totalError) {
      throw new Error(`Failed to get total machine count: ${totalError.message}`)
    }

    // Get active count
    const { count: active, error: activeError } = await this.supabase
      .from('machines')
      .select('*', { count: 'exact', head: true })
      .eq('is_active', true)

    if (activeError) {
      throw new Error(`Failed to get active machine count: ${activeError.message}`)
    }

    // Get status counts
    const { data: statusCounts, error: statusError } = await this.supabase
      .from('machines')
      .select('status')

    if (statusError) {
      throw new Error(`Failed to get machine status counts: ${statusError.message}`)
    }

    const statusMap = statusCounts?.reduce((acc, machine) => {
      const status = machine.status || 'offline'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>) || {}

    return {
      total: total || 0,
      active: active || 0,
      available: statusMap['available'] || 0,
      busy: statusMap['busy'] || 0,
      maintenance: statusMap['maintenance'] || 0,
      offline: statusMap['offline'] || 0,
    }
  }
}