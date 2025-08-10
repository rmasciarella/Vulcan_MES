import { SupabaseClient } from '@supabase/supabase-js'
import { Database, Tables } from '@/types/supabase'
import { WorkCellRepository } from '@/core/domains/resources/repositories/resource-repository-interfaces'
import { WorkCell } from '@/core/domains/resources/entities/WorkCell'
import { UnitOfWork, UnitOfWorkRepository } from '@/core/shared/unit-of-work'
import { WorkCellId } from '@/core/domains/resources/value-objects/resource-identifiers'
import { WorkCellCapacity } from '@/core/domains/resources/value-objects/capacity'
import { DepartmentCode } from '@/core/domains/resources/value-objects/department-code'
// import { ResourceNotFoundError } from '@/core/domains/resources/errors/resource-errors'
import { Version } from '@/core/shared/kernel/aggregate-root'
import { domainLogger } from '@/core/shared/logger'

type WorkCellRow = Tables<'work_cells'>
type WorkCellInsert = Database['public']['Tables']['work_cells']['Insert']
type WorkCellUpdate = Database['public']['Tables']['work_cells']['Update']

/**
 * Data mapper for converting between domain objects and database rows
 */
class WorkCellDataMapper {
  /**
   * Convert database row to domain WorkCell entity
   */
  static toDomain(row: WorkCellRow): WorkCell {
    const version = row.version ? Version.fromNumber(row.version) : Version.initial()

    return WorkCell.fromPersistence({
      id: WorkCellId.fromString(row.id),
      name: row.name,
      description: row.description || undefined,
      capacity: WorkCellCapacity.create(row.max_concurrent_tasks || 1),
      departmentCode: DepartmentCode.create(row.department_code as 'MS' | 'FH' | 'OB'),
      isActive: row.is_active ?? true,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: version.toNumber(),
    })
  }

  /**
   * Convert domain WorkCell entity to database insert object
   */
  static toInsert(workCell: WorkCell): WorkCellInsert {
    return {
      id: workCell.id.toString(),
      name: workCell.name,
      description: workCell.description || null,
      max_concurrent_tasks: workCell.capacity.maxConcurrentTasks,
      department_code: workCell.departmentCode.toString(),
      is_active: workCell.isActive,
      created_at: workCell.createdAt.toISOString(),
      updated_at: workCell.updatedAt.toISOString(),
      version: workCell.version.toNumber(),
    }
  }

  /**
   * Convert domain WorkCell entity to database update object
   */
  static toUpdate(workCell: WorkCell): WorkCellUpdate {
    return {
      name: workCell.name,
      description: workCell.description || null,
      max_concurrent_tasks: workCell.capacity.maxConcurrentTasks,
      department_code: workCell.departmentCode.toString(),
      is_active: workCell.isActive,
      updated_at: workCell.updatedAt.toISOString(),
      version: workCell.version.toNumber(),
    }
  }
}

/**
 * Supabase implementation of WorkCellRepository
 * Handles persistence and querying of WorkCell entities
 */
export class SupabaseWorkCellRepository implements WorkCellRepository, UnitOfWorkRepository {
  constructor(
    private readonly supabase: SupabaseClient<Database>,
    private readonly logger = domainLogger.child({ component: 'SupabaseWorkCellRepository' }),
  ) {}

  async findById(id: WorkCellId): Promise<WorkCell | null> {
    this.logger.debug({ workCellId: id.toString() }, 'Finding WorkCell by ID')

    try {
      const { data, error } = await this.supabase
        .from('work_cells')
        .select('*')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          // No rows returned
          return null
        }
        throw new Error(`Failed to find WorkCell: ${error.message}`)
      }

      const workCell = WorkCellDataMapper.toDomain(data)
      this.logger.debug(
        { workCellId: id.toString(), name: workCell.name },
        'WorkCell found successfully',
      )

      return workCell
    } catch (error) {
      this.logger.error({ workCellId: id.toString(), error }, 'Failed to find WorkCell by ID')
      throw error
    }
  }

  async findByDepartmentCode(departmentCode: DepartmentCode): Promise<WorkCell[]> {
    this.logger.debug(
      { departmentCode: departmentCode.toString() },
      'Finding WorkCells by department',
    )

    try {
      const { data, error } = await this.supabase
        .from('work_cells')
        .select('*')
        .eq('department_code', departmentCode.toString())
        .order('name')

      if (error) {
        throw new Error(`Failed to find WorkCells by department: ${error.message}`)
      }

      const workCells = data.map(WorkCellDataMapper.toDomain)
      this.logger.debug(
        { departmentCode: departmentCode.toString(), count: workCells.length },
        'WorkCells found by department',
      )

      return workCells
    } catch (error) {
      this.logger.error(
        { departmentCode: departmentCode.toString(), error },
        'Failed to find WorkCells by department',
      )
      throw error
    }
  }

  async findActive(): Promise<WorkCell[]> {
    this.logger.debug('Finding active WorkCells')

    try {
      const { data, error } = await this.supabase
        .from('work_cells')
        .select('*')
        .eq('is_active', true)
        .order('name')

      if (error) {
        throw new Error(`Failed to find active WorkCells: ${error.message}`)
      }

      const workCells = data.map(WorkCellDataMapper.toDomain)
      this.logger.debug({ count: workCells.length }, 'Active WorkCells found')

      return workCells
    } catch (error) {
      this.logger.error({ error }, 'Failed to find active WorkCells')
      throw error
    }
  }

  async findWithAvailableCapacity(minimumCapacity: number): Promise<WorkCell[]> {
    this.logger.debug({ minimumCapacity }, 'Finding WorkCells with available capacity')

    try {
      const { data, error } = await this.supabase
        .from('work_cells')
        .select('*')
        .eq('is_active', true)
        .gte('max_concurrent_tasks', minimumCapacity)
        .order('max_concurrent_tasks', { ascending: false })

      if (error) {
        throw new Error(`Failed to find WorkCells with capacity: ${error.message}`)
      }

      const workCells = data.map(WorkCellDataMapper.toDomain)
      this.logger.debug(
        { minimumCapacity, count: workCells.length },
        'WorkCells with available capacity found',
      )

      return workCells
    } catch (error) {
      this.logger.error(
        { minimumCapacity, error },
        'Failed to find WorkCells with available capacity',
      )
      throw error
    }
  }

  async save(workCell: WorkCell): Promise<void> {
    this.logger.debug(
      { workCellId: workCell.id.toString(), name: workCell.name },
      'Saving WorkCell',
    )

    try {
      const exists = await this.exists(workCell.id)

      if (exists) {
        // Update existing WorkCell
        const updateData = WorkCellDataMapper.toUpdate(workCell)
        const { error } = await this.supabase
          .from('work_cells')
          .update(updateData)
          .eq('id', workCell.id.toString())

        if (error) {
          throw new Error(`Failed to update WorkCell: ${error.message}`)
        }

        this.logger.debug({ workCellId: workCell.id.toString() }, 'WorkCell updated successfully')
      } else {
        // Insert new WorkCell
        const insertData = WorkCellDataMapper.toInsert(workCell)
        const { error } = await this.supabase.from('work_cells').insert(insertData)

        if (error) {
          throw new Error(`Failed to insert WorkCell: ${error.message}`)
        }

        this.logger.debug({ workCellId: workCell.id.toString() }, 'WorkCell inserted successfully')
      }

      // Publish domain events after successful persistence
      const events = workCell.getUncommittedEvents()
      for (const event of events) {
        this.logger.debug(
          {
            workCellId: workCell.id.toString(),
            eventType: event.eventType,
            aggregateId: event.aggregateId,
          },
          'Publishing WorkCell domain event',
        )
        // TODO: Implement event publishing when event system is ready
      }

      // Mark events as committed
      workCell.markEventsAsCommitted()
    } catch (error) {
      this.logger.error({ workCellId: workCell.id.toString(), error }, 'Failed to save WorkCell')
      throw error
    }
  }

  async delete(id: WorkCellId): Promise<void> {
    this.logger.debug({ workCellId: id.toString() }, 'Deleting WorkCell')

    try {
      const { error } = await this.supabase.from('work_cells').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete WorkCell: ${error.message}`)
      }

      this.logger.debug({ workCellId: id.toString() }, 'WorkCell deleted successfully')
    } catch (error) {
      this.logger.error({ workCellId: id.toString(), error }, 'Failed to delete WorkCell')
      throw error
    }
  }

  async exists(id: WorkCellId): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('work_cells')
        .select('id')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false // No rows returned
        }
        throw new Error(`Failed to check WorkCell existence: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error({ workCellId: id.toString(), error }, 'Failed to check WorkCell existence')
      throw error
    }
  }

  // UnitOfWorkRepository implementation
  async commitWork(unitOfWork: UnitOfWork): Promise<void> {
    this.logger.debug('Committing WorkCell unit of work')

    const workCells = unitOfWork.getAggregatesByType('WorkCell') as WorkCell[]

    for (const workCell of workCells) {
      await this.save(workCell)
    }

    this.logger.debug({ count: workCells.length }, 'WorkCell unit of work committed')
  }
}
