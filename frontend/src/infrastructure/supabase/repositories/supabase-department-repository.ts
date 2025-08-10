import { SupabaseClient } from '@supabase/supabase-js'
import { Database, Tables } from '@/types/supabase'
import { DepartmentRepository } from '@/core/domains/resources/repositories/resource-repository-interfaces'
import {
  Department,
  DepartmentSkillRequirement,
} from '@/core/domains/resources/entities/Department'
import { UnitOfWork, UnitOfWorkRepository } from '@/core/shared/unit-of-work'
import { DepartmentId } from '@/core/domains/resources/value-objects/resource-identifiers'
import { SkillLevel } from '@/core/domains/resources/value-objects/skill-level'
import { DepartmentCode } from '@/core/domains/resources/value-objects/department-code'
import { TimeWindow } from '@/core/domains/resources/value-objects/capacity'
// import { ResourceNotFoundError } from '@/core/domains/resources/errors/resource-errors'
import { Version } from '@/core/shared/kernel/aggregate-root'
import { domainLogger } from '@/core/shared/logger'

type DepartmentRow = Tables<'departments'>
type DepartmentInsert = Database['public']['Tables']['departments']['Insert']
type DepartmentUpdate = Database['public']['Tables']['departments']['Update']

/**
 * Data mapper for converting between domain objects and database rows
 */
class DepartmentDataMapper {
  /**
   * Convert database row to domain Department entity
   */
  static toDomain(row: DepartmentRow): Department {
    const version = row.version ? Version.fromNumber(row.version) : Version.initial()

    // Parse skill requirements from JSON if stored
    const skillRequirements: DepartmentSkillRequirement[] = []
    if (row.skill_requirements) {
      try {
        const skillsData = JSON.parse(row.skill_requirements as string)
        if (Array.isArray(skillsData)) {
          skillsData.forEach((s) => {
            if (s.skillType && s.minimumLevel) {
              skillRequirements.push({
                skillType: s.skillType,
                minimumLevel: SkillLevel.create(s.minimumLevel),
                isRequired: s.isRequired ?? true,
                description: s.description,
              })
            }
          })
        }
      } catch (error) {
        // Log error but continue with empty skill requirements
        domainLogger.warn(
          { departmentId: row.id, error },
          'Failed to parse department skill requirements',
        )
      }
    }

    // Parse business hours from JSON if stored
    let businessHours: TimeWindow
    if (row.business_hours) {
      try {
        const hoursData = JSON.parse(row.business_hours as string)
        if (hoursData.start && hoursData.end) {
          businessHours = TimeWindow.create(new Date(hoursData.start), new Date(hoursData.end))
        } else {
          // Default business hours: 7 AM - 4 PM on a Monday
          const defaultStart = new Date('2024-01-01T07:00:00Z') // Monday 7 AM
          const defaultEnd = new Date('2024-01-01T16:00:00Z') // Monday 4 PM
          businessHours = TimeWindow.create(defaultStart, defaultEnd)
        }
      } catch (error) {
        // Default business hours on error
        const defaultStart = new Date('2024-01-01T07:00:00Z') // Monday 7 AM
        const defaultEnd = new Date('2024-01-01T16:00:00Z') // Monday 4 PM
        businessHours = TimeWindow.create(defaultStart, defaultEnd)
        domainLogger.warn(
          { departmentId: row.id, error },
          'Failed to parse business hours, using defaults',
        )
      }
    } else {
      // Default business hours if not stored
      const defaultStart = new Date('2024-01-01T07:00:00Z') // Monday 7 AM
      const defaultEnd = new Date('2024-01-01T16:00:00Z') // Monday 4 PM
      businessHours = TimeWindow.create(defaultStart, defaultEnd)
    }

    return Department.fromPersistence({
      id: DepartmentId.fromString(row.id),
      name: row.name,
      code: DepartmentCode.create(row.code as 'MS' | 'FH' | 'OB'),
      description: row.description || undefined,
      skillRequirements,
      businessHours,
      isActive: row.is_active ?? true,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: version.toNumber(),
    })
  }

  /**
   * Convert domain Department entity to database insert object
   */
  static toInsert(department: Department): DepartmentInsert {
    // Convert skill requirements to JSON
    const skillRequirementsJson = JSON.stringify(
      department.skillRequirements.map((s) => ({
        skillType: s.skillType,
        minimumLevel: s.minimumLevel.toString(),
        isRequired: s.isRequired,
        description: s.description,
      })),
    )

    // Convert business hours to JSON
    const businessHoursJson = JSON.stringify({
      start: department.businessHours.startTime.toISOString(),
      end: department.businessHours.endTime.toISOString(),
    })

    return {
      id: department.id.toString(),
      name: department.name,
      code: department.code.toString(),
      description: department.description || null,
      skill_requirements: skillRequirementsJson,
      business_hours: businessHoursJson,
      is_active: department.isActive,
      created_at: department.createdAt.toISOString(),
      updated_at: department.updatedAt.toISOString(),
      version: department.version.toNumber(),
    }
  }

  /**
   * Convert domain Department entity to database update object
   */
  static toUpdate(department: Department): DepartmentUpdate {
    // Convert skill requirements to JSON
    const skillRequirementsJson = JSON.stringify(
      department.skillRequirements.map((s) => ({
        skillType: s.skillType,
        minimumLevel: s.minimumLevel.toString(),
        isRequired: s.isRequired,
        description: s.description,
      })),
    )

    // Convert business hours to JSON
    const businessHoursJson = JSON.stringify({
      start: department.businessHours.startTime.toISOString(),
      end: department.businessHours.endTime.toISOString(),
    })

    return {
      name: department.name,
      code: department.code.toString(),
      description: department.description || null,
      skill_requirements: skillRequirementsJson,
      business_hours: businessHoursJson,
      is_active: department.isActive,
      updated_at: department.updatedAt.toISOString(),
      version: department.version.toNumber(),
    }
  }
}

/**
 * Supabase implementation of DepartmentRepository
 * Handles persistence and querying of Department entities
 */
export class SupabaseDepartmentRepository implements DepartmentRepository, UnitOfWorkRepository {
  constructor(
    private readonly supabase: SupabaseClient<Database>,
    private readonly logger = domainLogger.child({ component: 'SupabaseDepartmentRepository' }),
  ) {}

  async findById(id: DepartmentId): Promise<Department | null> {
    this.logger.debug({ departmentId: id.toString() }, 'Finding Department by ID')

    try {
      const { data, error } = await this.supabase
        .from('departments')
        .select('*')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to find Department: ${error.message}`)
      }

      const department = DepartmentDataMapper.toDomain(data)
      this.logger.debug(
        { departmentId: id.toString(), name: department.name },
        'Department found successfully',
      )

      return department
    } catch (error) {
      this.logger.error({ departmentId: id.toString(), error }, 'Failed to find Department by ID')
      throw error
    }
  }

  async findByCode(code: DepartmentCode): Promise<Department | null> {
    this.logger.debug({ code: code.toString() }, 'Finding Department by code')

    try {
      const { data, error } = await this.supabase
        .from('departments')
        .select('*')
        .eq('code', code.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to find Department by code: ${error.message}`)
      }

      const department = DepartmentDataMapper.toDomain(data)
      this.logger.debug(
        { code: code.toString(), departmentId: department.id.toString() },
        'Department found by code',
      )

      return department
    } catch (error) {
      this.logger.error({ code: code.toString(), error }, 'Failed to find Department by code')
      throw error
    }
  }

  async findAll(): Promise<Department[]> {
    this.logger.debug('Finding all Departments')

    try {
      const { data, error } = await this.supabase.from('departments').select('*').order('code')

      if (error) {
        throw new Error(`Failed to find all Departments: ${error.message}`)
      }

      const departments = data.map(DepartmentDataMapper.toDomain)
      this.logger.debug({ count: departments.length }, 'All Departments found')

      return departments
    } catch (error) {
      this.logger.error({ error }, 'Failed to find all Departments')
      throw error
    }
  }

  async findActive(): Promise<Department[]> {
    this.logger.debug('Finding active Departments')

    try {
      const { data, error } = await this.supabase
        .from('departments')
        .select('*')
        .eq('is_active', true)
        .order('code')

      if (error) {
        throw new Error(`Failed to find active Departments: ${error.message}`)
      }

      const departments = data.map(DepartmentDataMapper.toDomain)
      this.logger.debug({ count: departments.length }, 'Active Departments found')

      return departments
    } catch (error) {
      this.logger.error({ error }, 'Failed to find active Departments')
      throw error
    }
  }

  async findWithSkillRequirement(skillType: string): Promise<Department[]> {
    this.logger.debug({ skillType }, 'Finding Departments with skill requirement')

    try {
      // Get all departments and filter by skill requirement in application code
      // This is necessary because JSON querying in Supabase can be complex
      const { data, error } = await this.supabase
        .from('departments')
        .select('*')
        .eq('is_active', true)
        .order('code')

      if (error) {
        throw new Error(`Failed to find Departments with skill requirement: ${error.message}`)
      }

      // Filter by skill requirement using domain logic
      const departments = data
        .map(DepartmentDataMapper.toDomain)
        .filter((department) =>
          department.skillRequirements.some((req) => req.skillType === skillType),
        )

      this.logger.debug(
        { skillType, count: departments.length },
        'Departments found with skill requirement',
      )

      return departments
    } catch (error) {
      this.logger.error({ skillType, error }, 'Failed to find Departments with skill requirement')
      throw error
    }
  }

  async save(department: Department): Promise<void> {
    this.logger.debug(
      { departmentId: department.id.toString(), name: department.name },
      'Saving Department',
    )

    try {
      const exists = await this.exists(department.id)

      if (exists) {
        // Update existing Department
        const updateData = DepartmentDataMapper.toUpdate(department)
        const { error } = await this.supabase
          .from('departments')
          .update(updateData)
          .eq('id', department.id.toString())

        if (error) {
          throw new Error(`Failed to update Department: ${error.message}`)
        }

        this.logger.debug(
          { departmentId: department.id.toString() },
          'Department updated successfully',
        )
      } else {
        // Insert new Department
        const insertData = DepartmentDataMapper.toInsert(department)
        const { error } = await this.supabase.from('departments').insert(insertData)

        if (error) {
          throw new Error(`Failed to insert Department: ${error.message}`)
        }

        this.logger.debug(
          { departmentId: department.id.toString() },
          'Department inserted successfully',
        )
      }

      // Publish domain events after successful persistence
      const events = department.getUncommittedEvents()
      for (const event of events) {
        this.logger.debug(
          {
            departmentId: department.id.toString(),
            eventType: event.eventType,
            aggregateId: event.aggregateId,
          },
          'Publishing Department domain event',
        )
        // TODO: Implement event publishing when event system is ready
      }

      // Mark events as committed
      department.markEventsAsCommitted()
    } catch (error) {
      this.logger.error(
        { departmentId: department.id.toString(), error },
        'Failed to save Department',
      )
      throw error
    }
  }

  async delete(id: DepartmentId): Promise<void> {
    this.logger.debug({ departmentId: id.toString() }, 'Deleting Department')

    try {
      const { error } = await this.supabase.from('departments').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete Department: ${error.message}`)
      }

      this.logger.debug({ departmentId: id.toString() }, 'Department deleted successfully')
    } catch (error) {
      this.logger.error({ departmentId: id.toString(), error }, 'Failed to delete Department')
      throw error
    }
  }

  async exists(id: DepartmentId): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('departments')
        .select('id')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false
        }
        throw new Error(`Failed to check Department existence: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error(
        { departmentId: id.toString(), error },
        'Failed to check Department existence',
      )
      throw error
    }
  }

  async existsByCode(code: DepartmentCode): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('departments')
        .select('id')
        .eq('code', code.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false
        }
        throw new Error(`Failed to check Department existence by code: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error(
        { code: code.toString(), error },
        'Failed to check Department existence by code',
      )
      throw error
    }
  }

  // UnitOfWorkRepository implementation
  async commitWork(unitOfWork: UnitOfWork): Promise<void> {
    this.logger.debug('Committing Department unit of work')

    const departments = unitOfWork.getAggregatesByType('Department') as Department[]

    for (const department of departments) {
      await this.save(department)
    }

    this.logger.debug({ count: departments.length }, 'Department unit of work committed')
  }
}
