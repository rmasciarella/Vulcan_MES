import { SupabaseClient } from '@supabase/supabase-js'
import { Database, Tables } from '@/types/supabase'
import { OperatorRepository } from '@/core/domains/resources/repositories/resource-repository-interfaces'
import { Operator, OperatorStatus, OperatorSkill } from '@/core/domains/resources/entities/Operator'
import { UnitOfWork, UnitOfWorkRepository } from '@/core/shared/unit-of-work'
import { OperatorId } from '@/core/domains/resources/value-objects/resource-identifiers'
import { SkillLevel } from '@/core/domains/resources/value-objects/skill-level'
import { TimeWindow } from '@/core/domains/resources/value-objects/capacity'
// import { ResourceNotFoundError } from '@/core/domains/resources/errors/resource-errors'
import { Version } from '@/core/shared/kernel/aggregate-root'
import { domainLogger } from '@/core/shared/logger'

type OperatorRow = Tables<'operators'>
type OperatorInsert = Database['public']['Tables']['operators']['Insert']
type OperatorUpdate = Database['public']['Tables']['operators']['Update']

/**
 * Data mapper for converting between domain objects and database rows
 */
class OperatorDataMapper {
  /**
   * Convert database row to domain Operator entity
   */
  static toDomain(row: OperatorRow): Operator {
    const version = row.version ? Version.fromNumber(row.version) : Version.initial()

    // Parse skills from JSON if stored
    const skills: OperatorSkill[] = []
    if (row.skills) {
      try {
        const skillsData = JSON.parse(row.skills as string)
        if (Array.isArray(skillsData)) {
          skillsData.forEach((s) => {
            if (s.skillType && s.level && s.certifiedAt) {
              skills.push({
                skillType: s.skillType,
                level: SkillLevel.create(s.level),
                certifiedAt: new Date(s.certifiedAt),
                expiresAt: s.expiresAt ? new Date(s.expiresAt) : undefined,
              })
            }
          })
        }
      } catch (error) {
        // Log error but continue with empty skills
        domainLogger.warn({ operatorId: row.id, error }, 'Failed to parse operator skills')
      }
    }

    return Operator.fromPersistence({
      id: OperatorId.fromString(row.id),
      firstName: row.first_name,
      lastName: row.last_name,
      employeeId: row.employee_id,
      departmentCode: DepartmentCode.create(row.department_code as 'MS' | 'FH' | 'OB'),
      skills,
      status: (row.status as OperatorStatus) || 'available',
      isActive: row.is_active ?? true,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: version.toNumber(),
    })
  }

  /**
   * Convert domain Operator entity to database insert object
   */
  static toInsert(operator: Operator): OperatorInsert {
    // Convert skills to JSON
    const skillsJson = JSON.stringify(
      operator.skills.map((s) => ({
        skillType: s.skillType,
        level: s.level.toString(),
        certifiedAt: s.certifiedAt.toISOString(),
        expiresAt: s.expiresAt?.toISOString(),
      })),
    )

    return {
      id: operator.id.toString(),
      first_name: operator.firstName,
      last_name: operator.lastName,
      employee_id: operator.employeeId,
      department_code: operator.departmentCode.toString(),
      skills: skillsJson,
      status: operator.status,
      is_active: operator.isActive,
      created_at: operator.createdAt.toISOString(),
      updated_at: operator.updatedAt.toISOString(),
      version: operator.version.toNumber(),
    }
  }

  /**
   * Convert domain Operator entity to database update object
   */
  static toUpdate(operator: Operator): OperatorUpdate {
    // Convert skills to JSON
    const skillsJson = JSON.stringify(
      operator.skills.map((s) => ({
        skillType: s.skillType,
        level: s.level.toString(),
        certifiedAt: s.certifiedAt.toISOString(),
        expiresAt: s.expiresAt?.toISOString(),
      })),
    )

    return {
      first_name: operator.firstName,
      last_name: operator.lastName,
      employee_id: operator.employeeId,
      department_code: operator.departmentCode.toString(),
      skills: skillsJson,
      status: operator.status,
      is_active: operator.isActive,
      updated_at: operator.updatedAt.toISOString(),
      version: operator.version.toNumber(),
    }
  }
}

/**
 * Supabase implementation of OperatorRepository
 * Handles persistence and querying of Operator entities
 */
export class SupabaseOperatorRepository implements OperatorRepository, UnitOfWorkRepository {
  constructor(
    private readonly supabase: SupabaseClient<Database>,
    private readonly logger = domainLogger.child({ component: 'SupabaseOperatorRepository' }),
  ) {}

  async findById(id: OperatorId): Promise<Operator | null> {
    this.logger.debug({ operatorId: id.toString() }, 'Finding Operator by ID')

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to find Operator: ${error.message}`)
      }

      const operator = OperatorDataMapper.toDomain(data)
      this.logger.debug(
        { operatorId: id.toString(), name: operator.getFullName() },
        'Operator found successfully',
      )

      return operator
    } catch (error) {
      this.logger.error({ operatorId: id.toString(), error }, 'Failed to find Operator by ID')
      throw error
    }
  }

  async findByEmployeeId(employeeId: string): Promise<Operator | null> {
    this.logger.debug({ employeeId }, 'Finding Operator by employee ID')

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('employee_id', employeeId)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to find Operator by employee ID: ${error.message}`)
      }

      const operator = OperatorDataMapper.toDomain(data)
      this.logger.debug(
        { employeeId, operatorId: operator.id.toString() },
        'Operator found by employee ID',
      )

      return operator
    } catch (error) {
      this.logger.error({ employeeId, error }, 'Failed to find Operator by employee ID')
      throw error
    }
  }

  async findByDepartmentCode(departmentCode: DepartmentCode): Promise<Operator[]> {
    this.logger.debug(
      { departmentCode: departmentCode.toString() },
      'Finding Operators by department',
    )

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('department_code', departmentCode.toString())
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find Operators by department: ${error.message}`)
      }

      const operators = data.map(OperatorDataMapper.toDomain)
      this.logger.debug(
        { departmentCode: departmentCode.toString(), count: operators.length },
        'Operators found by department',
      )

      return operators
    } catch (error) {
      this.logger.error(
        { departmentCode: departmentCode.toString(), error },
        'Failed to find Operators by department',
      )
      throw error
    }
  }

  async findBySkillLevel(skillType: string, minimumLevel: SkillLevel): Promise<Operator[]> {
    this.logger.debug(
      { skillType, minimumLevel: minimumLevel.toString() },
      'Finding Operators by skill level',
    )

    try {
      // Get all operators and filter by skill level in application code
      // This is necessary because JSON querying in Supabase can be complex
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('is_active', true)
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find Operators by skill level: ${error.message}`)
      }

      // Filter by skill level using domain logic
      const operators = data
        .map(OperatorDataMapper.toDomain)
        .filter((operator) => operator.hasSkillLevel(skillType, minimumLevel))

      this.logger.debug(
        { skillType, minimumLevel: minimumLevel.toString(), count: operators.length },
        'Operators found by skill level',
      )

      return operators
    } catch (error) {
      this.logger.error(
        { skillType, minimumLevel: minimumLevel.toString(), error },
        'Failed to find Operators by skill level',
      )
      throw error
    }
  }

  async findAvailableAt(timeWindow: TimeWindow): Promise<Operator[]> {
    this.logger.debug(
      {
        startTime: timeWindow.startTime.toISOString(),
        endTime: timeWindow.endTime.toISOString(),
      },
      'Finding available Operators',
    )

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('is_active', true)
        .eq('status', 'available')
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find available Operators: ${error.message}`)
      }

      // Filter by availability during time window (domain logic)
      const operators = data
        .map(OperatorDataMapper.toDomain)
        .filter((operator) => operator.isAvailableDuring(timeWindow))

      this.logger.debug(
        {
          timeWindow: {
            start: timeWindow.startTime.toISOString(),
            end: timeWindow.endTime.toISOString(),
          },
          count: operators.length,
        },
        'Available Operators found',
      )

      return operators
    } catch (error) {
      this.logger.error(
        {
          startTime: timeWindow.startTime.toISOString(),
          endTime: timeWindow.endTime.toISOString(),
          error,
        },
        'Failed to find available Operators',
      )
      throw error
    }
  }

  async findAvailableByDepartment(
    departmentCode: DepartmentCode,
    timeWindow: TimeWindow,
  ): Promise<Operator[]> {
    this.logger.debug(
      {
        departmentCode: departmentCode.toString(),
        startTime: timeWindow.startTime.toISOString(),
        endTime: timeWindow.endTime.toISOString(),
      },
      'Finding available Operators by department',
    )

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('department_code', departmentCode.toString())
        .eq('is_active', true)
        .eq('status', 'available')
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find available Operators by department: ${error.message}`)
      }

      // Filter by availability during time window (domain logic)
      const operators = data
        .map(OperatorDataMapper.toDomain)
        .filter((operator) => operator.isAvailableDuring(timeWindow))

      this.logger.debug(
        {
          departmentCode: departmentCode.toString(),
          timeWindow: {
            start: timeWindow.startTime.toISOString(),
            end: timeWindow.endTime.toISOString(),
          },
          count: operators.length,
        },
        'Available Operators found by department',
      )

      return operators
    } catch (error) {
      this.logger.error(
        {
          departmentCode: departmentCode.toString(),
          startTime: timeWindow.startTime.toISOString(),
          endTime: timeWindow.endTime.toISOString(),
          error,
        },
        'Failed to find available Operators by department',
      )
      throw error
    }
  }

  async findWithSkills(
    requiredSkills: Array<{ skillType: string; level: SkillLevel }>,
  ): Promise<Operator[]> {
    this.logger.debug(
      {
        requiredSkills: requiredSkills.map((s) => ({
          skillType: s.skillType,
          level: s.level.toString(),
        })),
      },
      'Finding Operators with required skills',
    )

    try {
      // Get all active operators and filter by skills in application code
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('is_active', true)
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find Operators with skills: ${error.message}`)
      }

      // Filter by skills using domain logic
      const operators = data
        .map(OperatorDataMapper.toDomain)
        .filter((operator) => operator.canPerformTask(requiredSkills))

      this.logger.debug(
        {
          requiredSkills: requiredSkills.map((s) => ({
            skillType: s.skillType,
            level: s.level.toString(),
          })),
          count: operators.length,
        },
        'Operators found with required skills',
      )

      return operators
    } catch (error) {
      this.logger.error({ requiredSkills, error }, 'Failed to find Operators with required skills')
      throw error
    }
  }

  async findActive(): Promise<Operator[]> {
    this.logger.debug('Finding active Operators')

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('is_active', true)
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find active Operators: ${error.message}`)
      }

      const operators = data.map(OperatorDataMapper.toDomain)
      this.logger.debug({ count: operators.length }, 'Active Operators found')

      return operators
    } catch (error) {
      this.logger.error({ error }, 'Failed to find active Operators')
      throw error
    }
  }

  async findByStatus(status: OperatorStatus): Promise<Operator[]> {
    this.logger.debug({ status }, 'Finding Operators by status')

    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('*')
        .eq('status', status)
        .order('last_name')
        .order('first_name')

      if (error) {
        throw new Error(`Failed to find Operators by status: ${error.message}`)
      }

      const operators = data.map(OperatorDataMapper.toDomain)
      this.logger.debug({ status, count: operators.length }, 'Operators found by status')

      return operators
    } catch (error) {
      this.logger.error({ status, error }, 'Failed to find Operators by status')
      throw error
    }
  }

  async save(operator: Operator): Promise<void> {
    this.logger.debug(
      { operatorId: operator.id.toString(), name: operator.getFullName() },
      'Saving Operator',
    )

    try {
      const exists = await this.exists(operator.id)

      if (exists) {
        // Update existing Operator
        const updateData = OperatorDataMapper.toUpdate(operator)
        const { error } = await this.supabase
          .from('operators')
          .update(updateData)
          .eq('id', operator.id.toString())

        if (error) {
          throw new Error(`Failed to update Operator: ${error.message}`)
        }

        this.logger.debug({ operatorId: operator.id.toString() }, 'Operator updated successfully')
      } else {
        // Insert new Operator
        const insertData = OperatorDataMapper.toInsert(operator)
        const { error } = await this.supabase.from('operators').insert(insertData)

        if (error) {
          throw new Error(`Failed to insert Operator: ${error.message}`)
        }

        this.logger.debug({ operatorId: operator.id.toString() }, 'Operator inserted successfully')
      }

      // Publish domain events after successful persistence
      const events = operator.getUncommittedEvents()
      for (const event of events) {
        this.logger.debug(
          {
            operatorId: operator.id.toString(),
            eventType: event.eventType,
            aggregateId: event.aggregateId,
          },
          'Publishing Operator domain event',
        )
        // TODO: Implement event publishing when event system is ready
      }

      // Mark events as committed
      operator.markEventsAsCommitted()
    } catch (error) {
      this.logger.error({ operatorId: operator.id.toString(), error }, 'Failed to save Operator')
      throw error
    }
  }

  async delete(id: OperatorId): Promise<void> {
    this.logger.debug({ operatorId: id.toString() }, 'Deleting Operator')

    try {
      const { error } = await this.supabase.from('operators').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete Operator: ${error.message}`)
      }

      this.logger.debug({ operatorId: id.toString() }, 'Operator deleted successfully')
    } catch (error) {
      this.logger.error({ operatorId: id.toString(), error }, 'Failed to delete Operator')
      throw error
    }
  }

  async exists(id: OperatorId): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('id')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false
        }
        throw new Error(`Failed to check Operator existence: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error({ operatorId: id.toString(), error }, 'Failed to check Operator existence')
      throw error
    }
  }

  async existsByEmployeeId(employeeId: string): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('operators')
        .select('id')
        .eq('employee_id', employeeId)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false
        }
        throw new Error(`Failed to check Operator existence by employee ID: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error({ employeeId, error }, 'Failed to check Operator existence by employee ID')
      throw error
    }
  }

  // UnitOfWorkRepository implementation
  async commitWork(unitOfWork: UnitOfWork): Promise<void> {
    this.logger.debug('Committing Operator unit of work')

    const operators = unitOfWork.getAggregatesByType('Operator') as Operator[]

    for (const operator of operators) {
      await this.save(operator)
    }

    this.logger.debug({ count: operators.length }, 'Operator unit of work committed')
  }
}
