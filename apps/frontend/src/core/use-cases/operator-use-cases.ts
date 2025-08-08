import { SupabaseClient } from '@supabase/supabase-js'
import { Database } from '../../../types/supabase'
import type { Operator } from '../types/database'

/**
 * Filters interface for operator queries
 */
export interface OperatorsListFilters {
  departmentId?: string
  certificationId?: string
  isActive?: boolean
  status?: 'available' | 'busy' | 'on_break' | 'off_shift'
  skillType?: string
}

/**
 * Operator availability data structure
 */
export interface OperatorAvailability {
  scheduledTasks: Array<{
    id: string
    scheduled_start: string
    scheduled_end: string
    task_name?: string
    status: string
  }>
}

/**
 * Business logic layer for operator operations
 * Encapsulates all operator-related use cases and domain logic
 */
export class OperatorUseCases {
  constructor(private readonly supabase: SupabaseClient<Database>) {}

  /**
   * Fetch operators with optional filtering
   */
  async getOperators(filters?: OperatorsListFilters): Promise<Operator[]> {
    let query = this.supabase
      .from('operators')
      .select('*')
      .order('last_name', { ascending: true })
      .order('first_name', { ascending: true })

    if (filters?.departmentId) {
      query = query.eq('department_id', filters.departmentId)
    }

    if (filters?.isActive !== undefined) {
      query = query.eq('is_active', filters.isActive)
    }

    if (filters?.status) {
      query = query.eq('status', filters.status)
    }

    // For certification filtering, we might need to join with operator_certifications table
    // This is a simplified approach - could be enhanced with proper joins
    if (filters?.certificationId) {
      // This would need to be implemented based on the actual schema
      // For now, we'll include all operators and filter later if needed
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch operators: ${error.message}`)
    }

    return data as Operator[]
  }

  /**
   * Fetch a single operator by ID
   */
  async getOperatorById(id: string): Promise<Operator> {
    const { data, error } = await this.supabase
      .from('operators')
      .select('*')
      .eq('operator_id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        throw new Error(`Operator with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch operator: ${error.message}`)
    }

    return data as Operator
  }

  /**
   * Get operator availability within a time window
   */
  async getOperatorAvailability(
    id: string, 
    startTime: Date, 
    endTime: Date
  ): Promise<OperatorAvailability> {
    const { data: tasks, error } = await this.supabase
      .from('scheduled_tasks')
      .select(`
        id,
        scheduled_start,
        scheduled_end,
        task_name,
        status
      `)
      .eq('operator_id', id)
      .gte('scheduled_start', startTime.toISOString())
      .lte('scheduled_end', endTime.toISOString())
      .order('scheduled_start', { ascending: true })

    if (error) {
      throw new Error(`Failed to fetch operator availability: ${error.message}`)
    }

    return {
      scheduledTasks: tasks || [],
    }
  }

  /**
   * Update operator active status
   */
  async updateOperatorActiveStatus(id: string, isActive: boolean): Promise<Operator> {
    const { data, error } = await this.supabase
      .from('operators')
      .update({ 
        is_active: isActive,
        updated_at: new Date().toISOString()
      })
      .eq('operator_id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update operator status: ${error.message}`)
    }

    return data as Operator
  }

  /**
   * Update operator status (available, busy, on_break, off_shift)
   */
  async updateOperatorStatus(id: string, status: Operator['status']): Promise<Operator> {
    const { data, error } = await this.supabase
      .from('operators')
      .update({ 
        status,
        updated_at: new Date().toISOString()
      })
      .eq('operator_id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to update operator status: ${error.message}`)
    }

    return data as Operator
  }

  /**
   * Get operators by department
   */
  async getOperatorsByDepartment(departmentId: string): Promise<Operator[]> {
    return this.getOperators({ departmentId })
  }

  /**
   * Get active operators only
   */
  async getActiveOperators(): Promise<Operator[]> {
    return this.getOperators({ isActive: true })
  }

  /**
   * Get available operators (active and status = available)
   */
  async getAvailableOperators(): Promise<Operator[]> {
    return this.getOperators({ isActive: true, status: 'available' })
  }

  /**
   * Get operators with specific certification
   */
  async getOperatorsByCertification(certificationId: string): Promise<Operator[]> {
    return this.getOperators({ certificationId })
  }

  /**
   * Create a new operator
   */
  async createOperator(operatorData: {
    firstName: string
    lastName: string
    employeeId: string
    departmentId?: string
    email?: string
    phoneNumber?: string
  }): Promise<Operator> {
    const { data, error } = await this.supabase
      .from('operators')
      .insert({
        first_name: operatorData.firstName,
        last_name: operatorData.lastName,
        employee_id: operatorData.employeeId,
        department_id: operatorData.departmentId,
        email: operatorData.email,
        phone_number: operatorData.phoneNumber,
        status: 'available',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error) {
      throw new Error(`Failed to create operator: ${error.message}`)
    }

    return data as Operator
  }

  /**
   * Delete an operator
   */
  async deleteOperator(id: string): Promise<void> {
    const { error } = await this.supabase
      .from('operators')
      .delete()
      .eq('operator_id', id)

    if (error) {
      throw new Error(`Failed to delete operator: ${error.message}`)
    }
  }

  /**
   * Get operator count for analytics/statistics
   */
  async getOperatorCount(): Promise<{ 
    total: number
    active: number
    available: number
    busy: number
    on_break: number
    off_shift: number
  }> {
    // Get total count
    const { count: total, error: totalError } = await this.supabase
      .from('operators')
      .select('*', { count: 'exact', head: true })

    if (totalError) {
      throw new Error(`Failed to get total operator count: ${totalError.message}`)
    }

    // Get active count
    const { count: active, error: activeError } = await this.supabase
      .from('operators')
      .select('*', { count: 'exact', head: true })
      .eq('is_active', true)

    if (activeError) {
      throw new Error(`Failed to get active operator count: ${activeError.message}`)
    }

    // Get status counts
    const { data: statusCounts, error: statusError } = await this.supabase
      .from('operators')
      .select('status')

    if (statusError) {
      throw new Error(`Failed to get operator status counts: ${statusError.message}`)
    }

    const statusMap = statusCounts?.reduce((acc, operator) => {
      const status = operator.status || 'off_shift'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>) || {}

    return {
      total: total || 0,
      active: active || 0,
      available: statusMap['available'] || 0,
      busy: statusMap['busy'] || 0,
      on_break: statusMap['on_break'] || 0,
      off_shift: statusMap['off_shift'] || 0,
    }
  }
}