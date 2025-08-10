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
import type { Operator, OperatorInsert, OperatorUpdate } from '@/core/types/database'
import { env } from '@/shared/lib/env'

/**
 * Operator availability data structure
 */
export interface OperatorAvailability {
  id: string
  start: Date
  end: Date
  available: boolean
  reason?: string
}

/**
 * Operator statistics response
 */
export interface OperatorStats {
  count: number
  active: number
  available: number
  onBreak?: number
}

/**
 * Operator list filters
 */
export interface OperatorsListFilters {
  departmentId?: string
  status?: string
  certificationId?: string
  isActive?: boolean
  shift?: string
}

/**
 * Operator API client with dual-mode support (Supabase + Backend)
 * Uses Supabase as primary data source, with future backend API fallback
 */
export class OperatorsAPI {
  private useBackendAPI: boolean
  private supabase = getSupabaseBrowserClient()

  constructor() {
    // Use backend API if configured, otherwise fallback to Supabase
    this.useBackendAPI = !!env.NEXT_PUBLIC_API_URL
  }

  /**
   * Fetch operators list with optional filtering
   */
  async getOperators(filters?: OperatorsListFilters): Promise<Operator[]> {
    if (this.useBackendAPI) {
      return this.getOperatorsFromBackend(filters)
    }
    return this.getOperatorsFromSupabase(filters)
  }

  /**
   * Fetch operators from backend API
   */
  private async getOperatorsFromBackend(filters?: OperatorsListFilters): Promise<Operator[]> {
    try {
      const queryParams = new URLSearchParams()
      if (filters?.departmentId) queryParams.set('department_id', filters.departmentId)
      if (filters?.status) queryParams.set('status', filters.status)
      if (filters?.certificationId) queryParams.set('certification_id', filters.certificationId)
      if (filters?.isActive !== undefined) queryParams.set('is_active', filters.isActive.toString())
      if (filters?.shift) queryParams.set('shift', filters.shift)

      const queryString = queryParams.toString()
      const path = `/api/v1/resources/operators${queryString ? `?${queryString}` : ''}`
      
      return await httpClient.get<Operator[]>(path)
    } catch (error) {
      throw new Error(`Failed to fetch operators from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch operators from Supabase
   */
  private async getOperatorsFromSupabase(filters?: OperatorsListFilters): Promise<Operator[]> {
    try {
      let query = this.supabase
        .from('operators')
        .select('*')
        .order('created_at', { ascending: false })

      // Apply filters
      if (filters?.departmentId) {
        query = query.eq('department_id', filters.departmentId)
      }
      if (filters?.status) {
        query = query.eq('status', filters.status)
      }
      if (filters?.isActive !== undefined) {
        query = query.eq('is_active', filters.isActive)
      }
      // Note: certification and shift filtering would need additional joins in real implementation

      const { data, error } = await query

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Operator[]
    } catch (error) {
      throw new Error(`Failed to fetch operators from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch single operator by ID
   */
  async getOperator(id: string): Promise<Operator> {
    if (this.useBackendAPI) {
      return this.getOperatorFromBackend(id)
    }
    return this.getOperatorFromSupabase(id)
  }

  /**
   * Fetch operator from backend API
   */
  private async getOperatorFromBackend(id: string): Promise<Operator> {
    try {
      return await httpClient.get<Operator>(`/api/v1/resources/operators/${id}`)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Operator with ID ${id} not found`)
      }
      throw new Error(`Failed to fetch operator from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Fetch operator from Supabase
   */
  private async getOperatorFromSupabase(id: string): Promise<Operator> {
    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('operator_id', id)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          throw new Error(`Operator with ID ${id} not found`)
        }
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Operator
    } catch (error) {
      throw new Error(`Failed to fetch operator from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Create new operator
   */
  async createOperator(operatorData: OperatorInsert): Promise<Operator> {
    if (this.useBackendAPI) {
      return this.createOperatorInBackend(operatorData)
    }
    return this.createOperatorInSupabase(operatorData)
  }

  /**
   * Create operator via backend API
   */
  private async createOperatorInBackend(operatorData: OperatorInsert): Promise<Operator> {
    try {
      return await httpClient.post<Operator>('/api/v1/resources/operators', operatorData)
    } catch (error) {
      throw new Error(`Failed to create operator in backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Create operator in Supabase
   */
  private async createOperatorInSupabase(operatorData: OperatorInsert): Promise<Operator> {
    try {
      const { data, error } = await this.supabase
        .from('operators')
        .insert(operatorData)
        .select()
        .single()

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Operator
    } catch (error) {
      throw new Error(`Failed to create operator in Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Update operator
   */
  async updateOperator(id: string, updateData: OperatorUpdate): Promise<Operator> {
    if (this.useBackendAPI) {
      return this.updateOperatorInBackend(id, updateData)
    }
    return this.updateOperatorInSupabase(id, updateData)
  }

  /**
   * Update operator via backend API
   */
  private async updateOperatorInBackend(id: string, updateData: OperatorUpdate): Promise<Operator> {
    try {
      return await httpClient.patch<Operator>(`/api/v1/resources/operators/${id}`, updateData)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Operator with ID ${id} not found`)
      }
      throw new Error(`Failed to update operator in backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Update operator in Supabase
   */
  private async updateOperatorInSupabase(id: string, updateData: OperatorUpdate): Promise<Operator> {
    try {
      const updates = {
        ...updateData,
        updated_at: new Date().toISOString(),
      }

      const { data, error } = await this.supabase
        .from('operators')
        .update(updates)
        .eq('operator_id', id)
        .select()
        .single()

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }

      return data as Operator
    } catch (error) {
      throw new Error(`Failed to update operator in Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Delete operator
   */
  async deleteOperator(id: string): Promise<void> {
    if (this.useBackendAPI) {
      return this.deleteOperatorFromBackend(id)
    }
    return this.deleteOperatorFromSupabase(id)
  }

  /**
   * Delete operator via backend API
   */
  private async deleteOperatorFromBackend(id: string): Promise<void> {
    try {
      await httpClient.delete(`/api/v1/resources/operators/${id}`)
    } catch (error) {
      if (error instanceof HttpError && error.status === 404) {
        throw new Error(`Operator with ID ${id} not found`)
      }
      throw new Error(`Failed to delete operator from backend: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Delete operator from Supabase
   */
  private async deleteOperatorFromSupabase(id: string): Promise<void> {
    try {
      const { error } = await this.supabase
        .from('operators')
        .delete()
        .eq('operator_id', id)

      if (error) {
        throw new Error(`Supabase error: ${error.message}`)
      }
    } catch (error) {
      throw new Error(`Failed to delete operator from Supabase: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Get operator availability for scheduling
   */
  async getOperatorAvailability(
    id: string, 
    start: Date, 
    end: Date
  ): Promise<OperatorAvailability[]> {
    if (this.useBackendAPI) {
      try {
        const queryParams = new URLSearchParams({
          start_time: start.toISOString(),
          end_time: end.toISOString(),
        })
        
        return await httpClient.get<OperatorAvailability[]>(
          `/api/v1/resources/operators/${id}/availability?${queryParams}`
        )
      } catch (error) {
        throw new Error(`Failed to fetch operator availability from backend: ${getErrorMessage(error)}`)
      }
    }

    // Supabase fallback - simplified availability check
    try {
      const operator = await this.getOperatorFromSupabase(id)
      
      // Simple availability based on operator status and active state
      const isAvailable = Boolean(operator.is_active && operator.status === 'working')
      
      const reasonText = !isAvailable ? `Operator is ${operator.status}` : undefined
      
      return [{
        id,
        start,
        end,
        available: isAvailable,
        ...(reasonText !== undefined && { reason: reasonText }),
      }]
    } catch (error) {
      throw new Error(`Failed to check operator availability: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Get operator statistics
   */
  async getOperatorStats(): Promise<OperatorStats> {
    if (this.useBackendAPI) {
      try {
        return await httpClient.get<OperatorStats>('/api/v1/resources/operators/stats')
      } catch (error) {
        throw new Error(`Failed to fetch operator stats from backend: ${getErrorMessage(error)}`)
      }
    }

    // Supabase fallback
    try {
      const operators = await this.getOperatorsFromSupabase()
      
      const active = operators.filter(o => o.is_active && o.status === 'working').length
      const available = operators.filter(o => 
        o.is_active && ['working', 'available'].includes(o.status || '')
      ).length
      const onBreak = operators.filter(o => o.status === 'break').length

      return {
        count: operators.length,
        active,
        available,
        onBreak,
      }
    } catch (error) {
      throw new Error(`Failed to calculate operator stats: ${getErrorMessage(error)}`)
    }
  }

  /**
   * Specialized queries for dashboard components
   */
  async getActiveOperators(): Promise<Operator[]> {
    return this.getOperators({ isActive: true })
  }

  async getAvailableOperators(): Promise<Operator[]> {
    return this.getOperators({ isActive: true, status: 'available' })
  }

  async getOperatorsByDepartment(departmentId: string): Promise<Operator[]> {
    return this.getOperators({ departmentId })
  }

  async getOperatorsByCertification(certificationId: string): Promise<Operator[]> {
    return this.getOperators({ certificationId })
  }

  /**
   * Update operator status (specialized method)
   */
  async updateOperatorStatus(id: string, status: Operator['status']): Promise<Operator> {
    return this.updateOperator(id, {
      ...(status !== undefined && status !== null && { status })
    })
  }

  /**
   * Update operator active status (specialized method)
   */
  async updateOperatorActiveStatus(id: string, isActive: boolean): Promise<Operator> {
    return this.updateOperator(id, { is_active: isActive })
  }
}

/**
 * Export singleton instance
 */
export const operatorsAPI = new OperatorsAPI()