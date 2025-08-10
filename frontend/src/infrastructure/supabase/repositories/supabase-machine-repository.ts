import { SupabaseClient } from '@supabase/supabase-js'
import { Database, Tables } from '@/types/supabase'
import { MachineRepository } from '@/core/domains/resources/repositories/resource-repository-interfaces'
import { Machine, MachineStatus } from '@/core/domains/resources/entities/Machine'
import { UnitOfWork, UnitOfWorkRepository } from '@/core/shared/unit-of-work'
import { MachineId, WorkCellId } from '@/core/domains/resources/value-objects/resource-identifiers'
import { TimeWindow } from '@/core/domains/resources/value-objects/capacity'
// import { ResourceNotFoundError } from '@/core/domains/resources/errors/resource-errors'
import { Version } from '@/core/shared/kernel/aggregate-root'
import { domainLogger } from '@/core/shared/logger'

type MachineRow = Tables<'machines'>
type MachineInsert = Database['public']['Tables']['machines']['Insert']
type MachineUpdate = Database['public']['Tables']['machines']['Update']

/**
 * Data mapper for converting between domain objects and database rows
 */
class MachineDataMapper {
  /**
   * Convert database row to domain Machine entity
   */
  static toDomain(row: MachineRow): Machine {
    const version = row.version ? Version.fromNumber(row.version) : Version.initial()

    // Parse maintenance windows from JSON if stored
    const maintenanceWindows: TimeWindow[] = []
    if (row.maintenance_windows) {
      try {
        const windowsData = JSON.parse(row.maintenance_windows as string)
        if (Array.isArray(windowsData)) {
          windowsData.forEach((w) => {
            if (w.start && w.end) {
              maintenanceWindows.push(TimeWindow.create(new Date(w.start), new Date(w.end)))
            }
          })
        }
      } catch (error) {
        // Log error but continue with empty maintenance windows
        domainLogger.warn({ machineId: row.id, error }, 'Failed to parse maintenance windows')
      }
    }

    return Machine.fromPersistence({
      id: MachineId.fromString(row.id),
      name: row.name,
      machineType: row.machine_type || 'Unknown',
      workCellId: WorkCellId.fromString(row.work_cell_id),
      serialNumber: row.serial_number || undefined,
      description: row.description || undefined,
      status: (row.status as MachineStatus) || 'available',
      isActive: row.is_active ?? true,
      maintenanceWindows,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      version: version.toNumber(),
    })
  }

  /**
   * Convert domain Machine entity to database insert object
   */
  static toInsert(machine: Machine): MachineInsert {
    // Convert maintenance windows to JSON
    const maintenanceWindowsJson = JSON.stringify(
      machine.maintenanceWindows.map((w) => ({
        start: w.startTime.toISOString(),
        end: w.endTime.toISOString(),
      })),
    )

    return {
      id: machine.id.toString(),
      name: machine.name,
      machine_type: machine.machineType,
      work_cell_id: machine.workCellId.toString(),
      serial_number: machine.serialNumber || null,
      description: machine.description || null,
      status: machine.status,
      is_active: machine.isActive,
      maintenance_windows: maintenanceWindowsJson,
      created_at: machine.createdAt.toISOString(),
      updated_at: machine.updatedAt.toISOString(),
      version: machine.version.toNumber(),
    }
  }

  /**
   * Convert domain Machine entity to database update object
   */
  static toUpdate(machine: Machine): MachineUpdate {
    // Convert maintenance windows to JSON
    const maintenanceWindowsJson = JSON.stringify(
      machine.maintenanceWindows.map((w) => ({
        start: w.startTime.toISOString(),
        end: w.endTime.toISOString(),
      })),
    )

    return {
      name: machine.name,
      machine_type: machine.machineType,
      work_cell_id: machine.workCellId.toString(),
      serial_number: machine.serialNumber || null,
      description: machine.description || null,
      status: machine.status,
      is_active: machine.isActive,
      maintenance_windows: maintenanceWindowsJson,
      updated_at: machine.updatedAt.toISOString(),
      version: machine.version.toNumber(),
    }
  }
}

/**
 * Supabase implementation of MachineRepository
 * Handles persistence and querying of Machine entities
 */
export class SupabaseMachineRepository implements MachineRepository, UnitOfWorkRepository {
  constructor(
    private readonly supabase: SupabaseClient<Database>,
    private readonly logger = domainLogger.child({ component: 'SupabaseMachineRepository' }),
  ) {}

  async findById(id: MachineId): Promise<Machine | null> {
    this.logger.debug({ machineId: id.toString() }, 'Finding Machine by ID')

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to find Machine: ${error.message}`)
      }

      const machine = MachineDataMapper.toDomain(data)
      this.logger.debug(
        { machineId: id.toString(), name: machine.name },
        'Machine found successfully',
      )

      return machine
    } catch (error) {
      this.logger.error({ machineId: id.toString(), error }, 'Failed to find Machine by ID')
      throw error
    }
  }

  async findByWorkCellId(workCellId: WorkCellId): Promise<Machine[]> {
    this.logger.debug({ workCellId: workCellId.toString() }, 'Finding Machines by WorkCell')

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('work_cell_id', workCellId.toString())
        .order('name')

      if (error) {
        throw new Error(`Failed to find Machines by WorkCell: ${error.message}`)
      }

      const machines = data.map(MachineDataMapper.toDomain)
      this.logger.debug(
        { workCellId: workCellId.toString(), count: machines.length },
        'Machines found by WorkCell',
      )

      return machines
    } catch (error) {
      this.logger.error(
        { workCellId: workCellId.toString(), error },
        'Failed to find Machines by WorkCell',
      )
      throw error
    }
  }

  async findByMachineType(machineType: string): Promise<Machine[]> {
    this.logger.debug({ machineType }, 'Finding Machines by type')

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('machine_type', machineType)
        .order('name')

      if (error) {
        throw new Error(`Failed to find Machines by type: ${error.message}`)
      }

      const machines = data.map(MachineDataMapper.toDomain)
      this.logger.debug({ machineType, count: machines.length }, 'Machines found by type')

      return machines
    } catch (error) {
      this.logger.error({ machineType, error }, 'Failed to find Machines by type')
      throw error
    }
  }

  async findAvailableAt(timeWindow: TimeWindow): Promise<Machine[]> {
    this.logger.debug(
      {
        startTime: timeWindow.startTime.toISOString(),
        endTime: timeWindow.endTime.toISOString(),
      },
      'Finding available Machines',
    )

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('is_active', true)
        .eq('status', 'available')
        .order('name')

      if (error) {
        throw new Error(`Failed to find available Machines: ${error.message}`)
      }

      // Filter by availability during time window (domain logic)
      const machines = data
        .map(MachineDataMapper.toDomain)
        .filter((machine) => machine.isAvailableDuring(timeWindow))

      this.logger.debug(
        {
          timeWindow: {
            start: timeWindow.startTime.toISOString(),
            end: timeWindow.endTime.toISOString(),
          },
          count: machines.length,
        },
        'Available Machines found',
      )

      return machines
    } catch (error) {
      this.logger.error(
        {
          startTime: timeWindow.startTime.toISOString(),
          endTime: timeWindow.endTime.toISOString(),
          error,
        },
        'Failed to find available Machines',
      )
      throw error
    }
  }

  async findAvailableByWorkCell(
    workCellId: WorkCellId,
    timeWindow: TimeWindow,
  ): Promise<Machine[]> {
    this.logger.debug(
      {
        workCellId: workCellId.toString(),
        startTime: timeWindow.startTime.toISOString(),
        endTime: timeWindow.endTime.toISOString(),
      },
      'Finding available Machines by WorkCell',
    )

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('work_cell_id', workCellId.toString())
        .eq('is_active', true)
        .eq('status', 'available')
        .order('name')

      if (error) {
        throw new Error(`Failed to find available Machines by WorkCell: ${error.message}`)
      }

      // Filter by availability during time window (domain logic)
      const machines = data
        .map(MachineDataMapper.toDomain)
        .filter((machine) => machine.isAvailableDuring(timeWindow))

      this.logger.debug(
        {
          workCellId: workCellId.toString(),
          timeWindow: {
            start: timeWindow.startTime.toISOString(),
            end: timeWindow.endTime.toISOString(),
          },
          count: machines.length,
        },
        'Available Machines found by WorkCell',
      )

      return machines
    } catch (error) {
      this.logger.error(
        {
          workCellId: workCellId.toString(),
          startTime: timeWindow.startTime.toISOString(),
          endTime: timeWindow.endTime.toISOString(),
          error,
        },
        'Failed to find available Machines by WorkCell',
      )
      throw error
    }
  }

  async findActive(): Promise<Machine[]> {
    this.logger.debug('Finding active Machines')

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('is_active', true)
        .order('name')

      if (error) {
        throw new Error(`Failed to find active Machines: ${error.message}`)
      }

      const machines = data.map(MachineDataMapper.toDomain)
      this.logger.debug({ count: machines.length }, 'Active Machines found')

      return machines
    } catch (error) {
      this.logger.error({ error }, 'Failed to find active Machines')
      throw error
    }
  }

  async findByStatus(status: MachineStatus): Promise<Machine[]> {
    this.logger.debug({ status }, 'Finding Machines by status')

    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('*')
        .eq('status', status)
        .order('name')

      if (error) {
        throw new Error(`Failed to find Machines by status: ${error.message}`)
      }

      const machines = data.map(MachineDataMapper.toDomain)
      this.logger.debug({ status, count: machines.length }, 'Machines found by status')

      return machines
    } catch (error) {
      this.logger.error({ status, error }, 'Failed to find Machines by status')
      throw error
    }
  }

  async save(machine: Machine): Promise<void> {
    this.logger.debug({ machineId: machine.id.toString(), name: machine.name }, 'Saving Machine')

    try {
      const exists = await this.exists(machine.id)

      if (exists) {
        // Update existing Machine
        const updateData = MachineDataMapper.toUpdate(machine)
        const { error } = await this.supabase
          .from('machines')
          .update(updateData)
          .eq('id', machine.id.toString())

        if (error) {
          throw new Error(`Failed to update Machine: ${error.message}`)
        }

        this.logger.debug({ machineId: machine.id.toString() }, 'Machine updated successfully')
      } else {
        // Insert new Machine
        const insertData = MachineDataMapper.toInsert(machine)
        const { error } = await this.supabase.from('machines').insert(insertData)

        if (error) {
          throw new Error(`Failed to insert Machine: ${error.message}`)
        }

        this.logger.debug({ machineId: machine.id.toString() }, 'Machine inserted successfully')
      }

      // Publish domain events after successful persistence
      const events = machine.getUncommittedEvents()
      for (const event of events) {
        this.logger.debug(
          {
            machineId: machine.id.toString(),
            eventType: event.eventType,
            aggregateId: event.aggregateId,
          },
          'Publishing Machine domain event',
        )
        // TODO: Implement event publishing when event system is ready
      }

      // Mark events as committed
      machine.markEventsAsCommitted()
    } catch (error) {
      this.logger.error({ machineId: machine.id.toString(), error }, 'Failed to save Machine')
      throw error
    }
  }

  async delete(id: MachineId): Promise<void> {
    this.logger.debug({ machineId: id.toString() }, 'Deleting Machine')

    try {
      const { error } = await this.supabase.from('machines').delete().eq('id', id.toString())

      if (error) {
        throw new Error(`Failed to delete Machine: ${error.message}`)
      }

      this.logger.debug({ machineId: id.toString() }, 'Machine deleted successfully')
    } catch (error) {
      this.logger.error({ machineId: id.toString(), error }, 'Failed to delete Machine')
      throw error
    }
  }

  async exists(id: MachineId): Promise<boolean> {
    try {
      const { data, error } = await this.supabase
        .from('machines')
        .select('id')
        .eq('id', id.toString())
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return false
        }
        throw new Error(`Failed to check Machine existence: ${error.message}`)
      }

      return data !== null
    } catch (error) {
      this.logger.error({ machineId: id.toString(), error }, 'Failed to check Machine existence')
      throw error
    }
  }

  // UnitOfWorkRepository implementation
  async commitWork(unitOfWork: UnitOfWork): Promise<void> {
    this.logger.debug('Committing Machine unit of work')

    const machines = unitOfWork.getAggregatesByType('Machine') as Machine[]

    for (const machine of machines) {
      await this.save(machine)
    }

    this.logger.debug({ count: machines.length }, 'Machine unit of work committed')
  }
}
