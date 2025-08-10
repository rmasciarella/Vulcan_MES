-- =====================================================
-- FOUNDATION: ENUMS AND DOMAINS
-- =====================================================

-- Create custom types for better type safety and documentation
CREATE TYPE job_status AS ENUM (
    'planned',
    'released',
    'in_progress',
    'completed',
    'on_hold',
    'cancelled'
);

CREATE TYPE task_status AS ENUM (
    'pending',      -- Not yet ready (waiting on precedence)
    'ready',        -- All prerequisites met, awaiting resources
    'scheduled',    -- Resources assigned, start time planned
    'in_progress',  -- Currently being executed
    'completed',    -- Successfully finished
    'cancelled',    -- Cancelled before completion
    'failed'        -- Failed during execution
);

CREATE TYPE machine_status AS ENUM (
    'available',
    'busy',
    'maintenance',
    'offline'
);

CREATE TYPE operator_status AS ENUM (
    'available',
    'assigned',
    'on_break',
    'off_shift',
    'absent'
);

CREATE TYPE skill_level AS ENUM ('1', '2', '3');

CREATE TYPE machine_automation_level AS ENUM (
    'attended',     -- Requires operator for full duration
    'unattended'    -- Requires operator for setup only
);

CREATE TYPE priority_level AS ENUM ('low', 'normal', 'high', 'critical');

-- =====================================================
-- CORE ENTITIES
-- =====================================================

-- Production zones for WIP management
CREATE TABLE production_zones (
    id BIGSERIAL PRIMARY KEY,
    zone_code VARCHAR(20) NOT NULL UNIQUE,
    zone_name VARCHAR(100) NOT NULL,
    wip_limit INTEGER NOT NULL CHECK (wip_limit > 0),
    current_wip INTEGER NOT NULL DEFAULT 0 CHECK (current_wip >= 0),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Standard operations (the 100 sequential operations)
CREATE TABLE operations (
    id BIGSERIAL PRIMARY KEY,
    operation_code VARCHAR(20) NOT NULL UNIQUE,
    operation_name VARCHAR(100) NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number BETWEEN 1 AND 100),
    production_zone_id BIGINT REFERENCES production_zones(id),
    is_critical BOOLEAN NOT NULL DEFAULT FALSE,  -- Part of critical sequence
    standard_duration_minutes INTEGER NOT NULL CHECK (standard_duration_minutes > 0),
    setup_duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK (setup_duration_minutes >= 0),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sequence_number)
);

-- Skills catalog
CREATE TABLE skills (
    id BIGSERIAL PRIMARY KEY,
    skill_code VARCHAR(20) NOT NULL UNIQUE,
    skill_name VARCHAR(100) NOT NULL,
    skill_category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Machines
CREATE TABLE machines (
    id BIGSERIAL PRIMARY KEY,
    machine_code VARCHAR(20) NOT NULL UNIQUE,
    machine_name VARCHAR(100) NOT NULL,
    automation_level machine_automation_level NOT NULL,
    production_zone_id BIGINT REFERENCES production_zones(id),
    status machine_status NOT NULL DEFAULT 'available',
    efficiency_factor DECIMAL(3,2) NOT NULL DEFAULT 1.00 CHECK (efficiency_factor BETWEEN 0.1 AND 2.0),
    is_bottleneck BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Machine capabilities (which operations each machine can perform)
CREATE TABLE machine_capabilities (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    operation_id BIGINT NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,  -- Primary vs alternative machine
    processing_time_minutes INTEGER NOT NULL CHECK (processing_time_minutes > 0),
    setup_time_minutes INTEGER NOT NULL DEFAULT 0 CHECK (setup_time_minutes >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(machine_id, operation_id)
);

-- Skills required for each machine
CREATE TABLE machine_required_skills (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    minimum_level skill_level NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(machine_id, skill_id)
);

-- Operators
CREATE TABLE operators (
    id BIGSERIAL PRIMARY KEY,
    employee_id VARCHAR(20) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    status operator_status NOT NULL DEFAULT 'available',
    default_shift_start TIME NOT NULL DEFAULT '07:00:00',
    default_shift_end TIME NOT NULL DEFAULT '16:00:00',
    lunch_start TIME NOT NULL DEFAULT '12:00:00',
    lunch_duration_minutes INTEGER NOT NULL DEFAULT 30,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Operator skills with proficiency levels
CREATE TABLE operator_skills (
    id BIGSERIAL PRIMARY KEY,
    operator_id BIGINT NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    skill_id BIGINT NOT NULL REFERENCES skills(id),
    proficiency_level skill_level NOT NULL,
    certified_date DATE,
    expiry_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(operator_id, skill_id),
    CHECK (expiry_date IS NULL OR expiry_date > certified_date)
);

-- Jobs (work orders in WIP)
CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    job_number VARCHAR(50) NOT NULL UNIQUE,
    customer_name VARCHAR(100),
    part_number VARCHAR(50),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    priority priority_level NOT NULL DEFAULT 'normal',
    status job_status NOT NULL DEFAULT 'planned',
    release_date TIMESTAMP,
    due_date TIMESTAMP NOT NULL,
    planned_start_date TIMESTAMP,
    planned_end_date TIMESTAMP,
    actual_start_date TIMESTAMP,
    actual_end_date TIMESTAMP,
    current_operation_sequence INTEGER,  -- Current position in routing
    notes TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (due_date > CURRENT_TIMESTAMP),
    CHECK (actual_end_date IS NULL OR actual_end_date >= actual_start_date),
    CHECK (planned_end_date IS NULL OR planned_end_date >= planned_start_date)
);

-- Tasks (instances of operations for specific jobs)
CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    operation_id BIGINT NOT NULL REFERENCES operations(id),
    sequence_in_job INTEGER NOT NULL CHECK (sequence_in_job > 0),
    status task_status NOT NULL DEFAULT 'pending',

    -- Planning data
    planned_start_time TIMESTAMP,
    planned_end_time TIMESTAMP,
    planned_duration_minutes INTEGER CHECK (planned_duration_minutes > 0),
    planned_setup_minutes INTEGER DEFAULT 0 CHECK (planned_setup_minutes >= 0),

    -- Execution data
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,
    actual_duration_minutes INTEGER CHECK (actual_duration_minutes > 0),
    actual_setup_minutes INTEGER CHECK (actual_setup_minutes >= 0),

    -- Resource assignments
    assigned_machine_id BIGINT REFERENCES machines(id),

    -- Tracking
    is_critical_path BOOLEAN NOT NULL DEFAULT FALSE,
    delay_minutes INTEGER DEFAULT 0 CHECK (delay_minutes >= 0),
    rework_count INTEGER DEFAULT 0 CHECK (rework_count >= 0),
    notes TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(job_id, sequence_in_job),
    CHECK (planned_end_time IS NULL OR planned_end_time > planned_start_time),
    CHECK (actual_end_time IS NULL OR actual_end_time > actual_start_time)
);

-- Task machine options (which machines CAN do this task)
CREATE TABLE task_machine_options (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    machine_id BIGINT NOT NULL REFERENCES machines(id),
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
    estimated_duration_minutes INTEGER NOT NULL CHECK (estimated_duration_minutes > 0),
    estimated_setup_minutes INTEGER DEFAULT 0 CHECK (estimated_setup_minutes >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, machine_id)
);

-- Task operator assignments
CREATE TABLE task_operator_assignments (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    operator_id BIGINT NOT NULL REFERENCES operators(id),
    assignment_type VARCHAR(20) NOT NULL CHECK (assignment_type IN ('setup', 'full_duration')),
    planned_start_time TIMESTAMP,
    planned_end_time TIMESTAMP,
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, operator_id, assignment_type)
);

-- =====================================================
-- TEMPORAL AND CALENDAR ENTITIES
-- =====================================================

-- Business calendar for holidays and special events
CREATE TABLE business_calendar (
    id BIGSERIAL PRIMARY KEY,
    calendar_date DATE NOT NULL UNIQUE,
    is_working_day BOOLEAN NOT NULL DEFAULT TRUE,
    holiday_name VARCHAR(100),
    working_hours_start TIME,
    working_hours_end TIME,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Operator availability (overrides default schedule)
CREATE TABLE operator_availability (
    id BIGSERIAL PRIMARY KEY,
    operator_id BIGINT NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    availability_date DATE NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    shift_start TIME,
    shift_end TIME,
    lunch_start TIME,
    lunch_duration_minutes INTEGER,
    reason VARCHAR(100),  -- vacation, sick, training, etc.
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(operator_id, availability_date)
);

-- Machine maintenance windows
CREATE TABLE machine_maintenance (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    maintenance_type VARCHAR(50) NOT NULL,  -- preventive, corrective, calibration
    planned_start_time TIMESTAMP NOT NULL,
    planned_end_time TIMESTAMP NOT NULL,
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,
    technician_name VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (planned_end_time > planned_start_time),
    CHECK (actual_end_time IS NULL OR actual_end_time > actual_start_time)
);

-- =====================================================
-- CONSTRAINT AND TRACKING ENTITIES
-- =====================================================

-- Task precedence constraints (beyond standard sequence)
CREATE TABLE task_precedence_constraints (
    id BIGSERIAL PRIMARY KEY,
    predecessor_task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    successor_task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    lag_time_minutes INTEGER NOT NULL DEFAULT 0,  -- Can be negative for lead
    constraint_type VARCHAR(20) NOT NULL DEFAULT 'finish_to_start',
    CHECK (constraint_type IN ('finish_to_start', 'start_to_start', 'finish_to_finish', 'start_to_finish')),
    CHECK (predecessor_task_id != successor_task_id),
    UNIQUE(predecessor_task_id, successor_task_id)
);

-- Critical operation sequences
CREATE TABLE critical_sequences (
    id BIGSERIAL PRIMARY KEY,
    sequence_name VARCHAR(100) NOT NULL,
    from_operation_sequence INTEGER NOT NULL,
    to_operation_sequence INTEGER NOT NULL,
    priority_boost INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (to_operation_sequence > from_operation_sequence),
    CHECK (from_operation_sequence BETWEEN 1 AND 100),
    CHECK (to_operation_sequence BETWEEN 1 AND 100)
);

-- Schedule snapshots for version control
CREATE TABLE schedule_versions (
    id BIGSERIAL PRIMARY KEY,
    version_number INTEGER NOT NULL UNIQUE,
    schedule_name VARCHAR(100),
    is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_by VARCHAR(50),
    approved_at TIMESTAMP,
    notes TEXT
);

-- Task schedule history (for tracking changes)
CREATE TABLE task_schedule_history (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    schedule_version_id BIGINT REFERENCES schedule_versions(id),
    old_planned_start TIMESTAMP,
    new_planned_start TIMESTAMP,
    old_planned_end TIMESTAMP,
    new_planned_end TIMESTAMP,
    old_machine_id BIGINT REFERENCES machines(id),
    new_machine_id BIGINT REFERENCES machines(id),
    change_reason VARCHAR(200),
    changed_by VARCHAR(50),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Job queries
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status IN ('released', 'in_progress');
CREATE INDEX idx_jobs_due_date ON jobs(due_date) WHERE status NOT IN ('completed', 'cancelled');
CREATE INDEX idx_jobs_priority ON jobs(priority, due_date) WHERE status IN ('released', 'in_progress');

-- Task queries
CREATE INDEX idx_tasks_job_id ON tasks(job_id);
CREATE INDEX idx_tasks_status ON tasks(status) WHERE status IN ('ready', 'scheduled', 'in_progress');
CREATE INDEX idx_tasks_operation_id ON tasks(operation_id);
CREATE INDEX idx_tasks_machine ON tasks(assigned_machine_id) WHERE assigned_machine_id IS NOT NULL;
CREATE INDEX idx_tasks_critical_path ON tasks(is_critical_path) WHERE is_critical_path = TRUE;
CREATE INDEX idx_tasks_planned_start ON tasks(planned_start_time) WHERE planned_start_time IS NOT NULL;

-- Resource availability queries
CREATE INDEX idx_operators_status ON operators(status) WHERE is_active = TRUE;
CREATE INDEX idx_operator_skills_lookup ON operator_skills(skill_id, proficiency_level);
CREATE INDEX idx_machines_status ON machines(status);
CREATE INDEX idx_machine_capabilities_operation ON machine_capabilities(operation_id);

-- Temporal queries
CREATE INDEX idx_operator_availability_date ON operator_availability(availability_date, operator_id);
CREATE INDEX idx_business_calendar_date ON business_calendar(calendar_date) WHERE is_working_day = TRUE;
CREATE INDEX idx_machine_maintenance_planned ON machine_maintenance(machine_id, planned_start_time, planned_end_time);

-- Assignment queries
CREATE INDEX idx_task_operator_assignments_operator ON task_operator_assignments(operator_id, planned_start_time);
CREATE INDEX idx_task_operator_assignments_task ON task_operator_assignments(task_id);

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- Resource utilization view
CREATE VIEW v_resource_utilization AS
WITH machine_util AS (
    SELECT
        m.id,
        m.machine_code,
        m.machine_name,
        m.status,
        COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'in_progress') as active_tasks,
        COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'scheduled'
            AND t.planned_start_time >= CURRENT_TIMESTAMP
            AND t.planned_start_time < CURRENT_TIMESTAMP + INTERVAL '8 hours') as scheduled_next_8h,
        AVG(CASE
            WHEN t.actual_end_time IS NOT NULL
            THEN EXTRACT(EPOCH FROM (t.actual_end_time - t.actual_start_time))/60.0
            ELSE NULL
        END) as avg_actual_duration_min
    FROM machines m
    LEFT JOIN tasks t ON t.assigned_machine_id = m.id
    GROUP BY m.id, m.machine_code, m.machine_name, m.status
),
operator_util AS (
    SELECT
        o.id,
        o.employee_id,
        o.first_name || ' ' || o.last_name as operator_name,
        o.status,
        COUNT(DISTINCT toa.task_id) FILTER (WHERE t.status = 'in_progress') as active_tasks,
        COUNT(DISTINCT toa.task_id) FILTER (WHERE t.status = 'scheduled'
            AND toa.planned_start_time >= CURRENT_TIMESTAMP
            AND toa.planned_start_time < CURRENT_TIMESTAMP + INTERVAL '8 hours') as scheduled_next_8h
    FROM operators o
    LEFT JOIN task_operator_assignments toa ON toa.operator_id = o.id
    LEFT JOIN tasks t ON t.id = toa.task_id
    WHERE o.is_active = TRUE
    GROUP BY o.id, o.employee_id, o.first_name, o.last_name, o.status
)
SELECT
    'machine' as resource_type,
    machine_code as resource_code,
    machine_name as resource_name,
    status::text,
    active_tasks,
    scheduled_next_8h,
    avg_actual_duration_min,
    NULL::INTEGER as skill_count
FROM machine_util
UNION ALL
SELECT
    'operator' as resource_type,
    employee_id as resource_code,
    operator_name as resource_name,
    status::text,
    active_tasks,
    scheduled_next_8h,
    NULL::NUMERIC as avg_actual_duration_min,
    (SELECT COUNT(*) FROM operator_skills os WHERE os.operator_id = operator_util.id) as skill_count
FROM operator_util;

-- Critical path view
CREATE VIEW v_critical_path AS
WITH RECURSIVE task_paths AS (
    -- Start with tasks that have no predecessors
    SELECT
        t.id,
        t.job_id,
        t.sequence_in_job,
        t.planned_duration_minutes as path_duration,
        ARRAY[t.id] as path,
        t.planned_end_time as path_end_time
    FROM tasks t
    WHERE NOT EXISTS (
        SELECT 1 FROM task_precedence_constraints tpc
        WHERE tpc.successor_task_id = t.id
    )
    AND t.sequence_in_job = 1

    UNION ALL

    -- Recursively add successor tasks
    SELECT
        t.id,
        t.job_id,
        t.sequence_in_job,
        tp.path_duration + t.planned_duration_minutes + COALESCE(tpc.lag_time_minutes, 0),
        tp.path || t.id,
        t.planned_end_time
    FROM task_paths tp
    JOIN tasks t ON t.job_id = tp.job_id AND t.sequence_in_job = tp.sequence_in_job + 1
    LEFT JOIN task_precedence_constraints tpc ON tpc.predecessor_task_id = tp.id AND tpc.successor_task_id = t.id
    WHERE t.sequence_in_job <= 100
)
SELECT
    j.job_number,
    j.due_date,
    MAX(tp.path_duration) as critical_path_duration,
    MAX(tp.path_end_time) as critical_path_end,
    CASE
        WHEN MAX(tp.path_end_time) > j.due_date
        THEN EXTRACT(EPOCH FROM (MAX(tp.path_end_time) - j.due_date))/3600.0
        ELSE 0
    END as tardiness_hours,
    (SELECT array_agg(task_id)
     FROM unnest(path) as task_id
     WHERE path_duration = MAX(tp.path_duration)) as critical_tasks
FROM task_paths tp
JOIN jobs j ON j.id = tp.job_id
WHERE j.status IN ('released', 'in_progress')
GROUP BY j.id, j.job_number, j.due_date;

-- Tardy jobs view
CREATE VIEW v_tardy_jobs AS
SELECT
    j.id,
    j.job_number,
    j.customer_name,
    j.priority,
    j.due_date,
    j.planned_end_date,
    j.actual_end_date,
    CASE
        WHEN j.actual_end_date IS NOT NULL THEN
            GREATEST(0, EXTRACT(EPOCH FROM (j.actual_end_date - j.due_date))/3600.0)
        WHEN j.planned_end_date IS NOT NULL THEN
            GREATEST(0, EXTRACT(EPOCH FROM (j.planned_end_date - j.due_date))/3600.0)
        ELSE
            GREATEST(0, EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - j.due_date))/3600.0)
    END as tardiness_hours,
    COUNT(t.id) FILTER (WHERE t.status = 'completed') as completed_tasks,
    COUNT(t.id) as total_tasks,
    j.current_operation_sequence
FROM jobs j
LEFT JOIN tasks t ON t.job_id = j.id
WHERE j.status NOT IN ('completed', 'cancelled')
  AND (
    (j.actual_end_date IS NOT NULL AND j.actual_end_date > j.due_date) OR
    (j.planned_end_date IS NOT NULL AND j.planned_end_date > j.due_date) OR
    (j.actual_end_date IS NULL AND j.planned_end_date IS NULL AND CURRENT_TIMESTAMP > j.due_date)
  )
GROUP BY j.id, j.job_number, j.customer_name, j.priority, j.due_date,
         j.planned_end_date, j.actual_end_date, j.current_operation_sequence
ORDER BY tardiness_hours DESC;

-- Operator skill matrix view
CREATE VIEW v_operator_skill_matrix AS
SELECT
    o.employee_id,
    o.first_name || ' ' || o.last_name as operator_name,
    s.skill_code,
    s.skill_name,
    os.proficiency_level,
    os.certified_date,
    os.expiry_date,
    CASE
        WHEN os.expiry_date IS NOT NULL AND os.expiry_date < CURRENT_DATE
        THEN 'expired'
        WHEN os.expiry_date IS NOT NULL AND os.expiry_date < CURRENT_DATE + INTERVAL '30 days'
        THEN 'expiring_soon'
        ELSE 'valid'
    END as certification_status
FROM operators o
CROSS JOIN skills s
LEFT JOIN operator_skills os ON os.operator_id = o.id AND os.skill_id = s.id
WHERE o.is_active = TRUE
ORDER BY o.employee_id, s.skill_code;

-- WIP by zone view
CREATE VIEW v_wip_by_zone AS
SELECT
    pz.zone_code,
    pz.zone_name,
    pz.wip_limit,
    COUNT(DISTINCT t.job_id) as current_wip,
    pz.wip_limit - COUNT(DISTINCT t.job_id) as available_capacity,
    CASE
        WHEN COUNT(DISTINCT t.job_id) >= pz.wip_limit THEN 'at_limit'
        WHEN COUNT(DISTINCT t.job_id) >= pz.wip_limit * 0.9 THEN 'near_limit'
        ELSE 'ok'
    END as zone_status,
    array_agg(DISTINCT j.job_number) as jobs_in_zone
FROM production_zones pz
LEFT JOIN operations op ON op.production_zone_id = pz.id
LEFT JOIN tasks t ON t.operation_id = op.id AND t.status IN ('ready', 'scheduled', 'in_progress')
LEFT JOIN jobs j ON j.id = t.job_id
GROUP BY pz.id, pz.zone_code, pz.zone_name, pz.wip_limit;

-- =====================================================
-- TRIGGERS FOR CONSISTENCY
-- =====================================================

-- Update job progress when tasks complete
CREATE OR REPLACE FUNCTION update_job_progress()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        -- Update current operation sequence
        UPDATE jobs
        SET current_operation_sequence = NEW.sequence_in_job,
            status = CASE
                WHEN NEW.sequence_in_job = 100 THEN 'completed'::job_status
                WHEN status = 'planned' THEN 'in_progress'::job_status
                ELSE status
            END,
            actual_start_date = COALESCE(actual_start_date, NEW.actual_start_time),
            actual_end_date = CASE
                WHEN NEW.sequence_in_job = 100 THEN NEW.actual_end_time
                ELSE actual_end_date
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.job_id;

        -- Mark next task as ready if all predecessors complete
        UPDATE tasks
        SET status = 'ready'::task_status
        WHERE job_id = NEW.job_id
          AND sequence_in_job = NEW.sequence_in_job + 1
          AND status = 'pending'::task_status;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_job_progress
AFTER UPDATE OF status ON tasks
FOR EACH ROW
EXECUTE FUNCTION update_job_progress();

-- Update WIP counts in zones
CREATE OR REPLACE FUNCTION update_zone_wip()
RETURNS TRIGGER AS $$
BEGIN
    -- Update old zone if task moved out
    IF OLD.status IN ('ready', 'scheduled', 'in_progress')
       AND NEW.status NOT IN ('ready', 'scheduled', 'in_progress') THEN
        UPDATE production_zones
        SET current_wip = GREATEST(0, current_wip - 1)
        WHERE id = (SELECT production_zone_id FROM operations WHERE id = OLD.operation_id);
    END IF;

    -- Update new zone if task moved in
    IF OLD.status NOT IN ('ready', 'scheduled', 'in_progress')
       AND NEW.status IN ('ready', 'scheduled', 'in_progress') THEN
        UPDATE production_zones
        SET current_wip = current_wip + 1
        WHERE id = (SELECT production_zone_id FROM operations WHERE id = NEW.operation_id);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_zone_wip
AFTER UPDATE OF status ON tasks
FOR EACH ROW
EXECUTE FUNCTION update_zone_wip();

-- Validate operator skills before assignment
CREATE OR REPLACE FUNCTION validate_operator_skills()
RETURNS TRIGGER AS $$
DECLARE
    required_skills RECORD;
    has_skill BOOLEAN;
BEGIN
    -- Only validate for new assignments
    IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.operator_id != NEW.operator_id) THEN
        -- Get machine for this task
        FOR required_skills IN
            SELECT mrs.skill_id, mrs.minimum_level
            FROM tasks t
            JOIN machine_required_skills mrs ON mrs.machine_id = t.assigned_machine_id
            WHERE t.id = NEW.task_id
        LOOP
            -- Check if operator has required skill at minimum level
            SELECT EXISTS (
                SELECT 1
                FROM operator_skills os
                WHERE os.operator_id = NEW.operator_id
                  AND os.skill_id = required_skills.skill_id
                  AND os.proficiency_level::text >= required_skills.minimum_level::text
                  AND (os.expiry_date IS NULL OR os.expiry_date >= CURRENT_DATE)
            ) INTO has_skill;

            IF NOT has_skill THEN
                RAISE EXCEPTION 'Operator lacks required skill or proficiency level for assigned machine';
            END IF;
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_operator_skills
BEFORE INSERT OR UPDATE ON task_operator_assignments
FOR EACH ROW
EXECUTE FUNCTION validate_operator_skills();

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_jobs_updated_at BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_operators_updated_at BEFORE UPDATE ON operators
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_machines_updated_at BEFORE UPDATE ON machines
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- SAMPLE DATA
-- =====================================================

-- Insert production zones
INSERT INTO production_zones (zone_code, zone_name, wip_limit) VALUES
('ZONE_A', 'Preparation Area', 5),
('ZONE_B', 'Primary Processing', 3),
('ZONE_C', 'Secondary Processing', 4),
('ZONE_D', 'Finishing Area', 3),
('ZONE_E', 'Quality Control', 2);

-- Insert skills
INSERT INTO skills (skill_code, skill_name, skill_category) VALUES
('LASER_OP', 'Laser Operation', 'Machine Operation'),
('CNC_PROG', 'CNC Programming', 'Programming'),
('QUALITY', 'Quality Inspection', 'Quality'),
('ASSEMBLY', 'Assembly', 'Manual'),
('MAINT', 'Maintenance', 'Technical');

-- Insert sample operations (first 10 of 100)
INSERT INTO operations (operation_code, operation_name, sequence_number, production_zone_id, is_critical, standard_duration_minutes, setup_duration_minutes) VALUES
('OP001', 'Material Preparation', 1, 1, false, 30, 10),
('OP002', 'Initial Inspection', 2, 1, false, 15, 5),
('OP003', 'Laser Processing', 3, 2, true, 45, 15),
('OP004', 'CNC Milling', 4, 2, true, 60, 20),
('OP005', 'Deburring', 5, 2, false, 20, 5),
('OP006', 'Heat Treatment', 6, 3, true, 120, 30),
('OP007', 'Surface Treatment', 7, 3, false, 40, 10),
('OP008', 'Precision Grinding', 8, 3, true, 50, 15),
('OP009', 'Assembly Step 1', 9, 4, false, 35, 10),
('OP010', 'Assembly Step 2', 10, 4, false, 35, 10);

-- Insert machines
INSERT INTO machines (machine_code, machine_name, automation_level, production_zone_id, efficiency_factor) VALUES
('LASER01', 'Laser System 1', 'attended', 2, 0.95),
('LASER02', 'Laser System 2', 'attended', 2, 1.00),
('CNC01', 'CNC Mill 1', 'unattended', 2, 0.90),
('CNC02', 'CNC Mill 2', 'unattended', 2, 0.85),
('HEAT01', 'Heat Treatment Oven', 'unattended', 3, 1.00),
('GRIND01', 'Precision Grinder', 'attended', 3, 0.92),
('ASSY01', 'Assembly Station 1', 'attended', 4, 1.00),
('ASSY02', 'Assembly Station 2', 'attended', 4, 0.95);

-- Insert machine capabilities
INSERT INTO machine_capabilities (machine_id, operation_id, is_primary, processing_time_minutes, setup_time_minutes) VALUES
(1, 3, true, 45, 15),   -- LASER01 can do laser processing (primary)
(2, 3, false, 48, 15),  -- LASER02 can do laser processing (alternative)
(3, 4, true, 60, 20),   -- CNC01 can do CNC milling (primary)
(4, 4, false, 70, 20),  -- CNC02 can do CNC milling (alternative)
(5, 6, true, 120, 30),  -- HEAT01 for heat treatment
(6, 8, true, 50, 15),   -- GRIND01 for precision grinding
(7, 9, true, 35, 10),   -- ASSY01 for assembly step 1
(7, 10, true, 35, 10),  -- ASSY01 for assembly step 2
(8, 9, false, 38, 10),  -- ASSY02 for assembly step 1 (alternative)
(8, 10, false, 38, 10); -- ASSY02 for assembly step 2 (alternative)

-- Insert machine required skills
INSERT INTO machine_required_skills (machine_id, skill_id, minimum_level) VALUES
(1, 1, '2'), -- LASER01 requires Laser Operation level 2
(2, 1, '2'), -- LASER02 requires Laser Operation level 2
(3, 2, '1'), -- CNC01 requires CNC Programming level 1
(4, 2, '1'), -- CNC02 requires CNC Programming level 1
(7, 4, '1'), -- ASSY01 requires Assembly level 1
(8, 4, '1'); -- ASSY02 requires Assembly level 1

-- Insert operators
INSERT INTO operators (employee_id, first_name, last_name, email) VALUES
('EMP001', 'John', 'Smith', 'john.smith@company.com'),
('EMP002', 'Jane', 'Doe', 'jane.doe@company.com'),
('EMP003', 'Bob', 'Johnson', 'bob.johnson@company.com'),
('EMP004', 'Alice', 'Williams', 'alice.williams@company.com'),
('EMP005', 'Charlie', 'Brown', 'charlie.brown@company.com'),
('EMP006', 'Diana', 'Miller', 'diana.miller@company.com'),
('EMP007', 'Edward', 'Davis', 'edward.davis@company.com'),
('EMP008', 'Fiona', 'Garcia', 'fiona.garcia@company.com'),
('EMP009', 'George', 'Martinez', 'george.martinez@company.com'),
('EMP010', 'Helen', 'Anderson', 'helen.anderson@company.com');

-- Insert operator skills
INSERT INTO operator_skills (operator_id, skill_id, proficiency_level, certified_date) VALUES
(1, 1, '3', '2023-01-15'), -- John: Expert in Laser
(1, 2, '2', '2023-03-20'), -- John: Intermediate in CNC
(2, 1, '2', '2023-02-10'), -- Jane: Intermediate in Laser
(2, 3, '3', '2023-01-05'), -- Jane: Expert in Quality
(3, 2, '3', '2022-11-30'), -- Bob: Expert in CNC
(3, 5, '2', '2023-04-15'), -- Bob: Intermediate in Maintenance
(4, 4, '2', '2023-02-28'), -- Alice: Intermediate in Assembly
(5, 4, '1', '2023-06-01'), -- Charlie: Beginner in Assembly
(6, 3, '2', '2023-03-10'), -- Diana: Intermediate in Quality
(7, 1, '1', '2023-07-01'), -- Edward: Beginner in Laser
(8, 2, '2', '2023-05-15'), -- Fiona: Intermediate in CNC
(9, 4, '3', '2022-12-01'), -- George: Expert in Assembly
(10, 5, '3', '2023-01-20'); -- Helen: Expert in Maintenance

-- Insert sample job
INSERT INTO jobs (job_number, customer_name, part_number, quantity, priority, status, due_date, release_date) VALUES
('JOB-2024-001', 'Acme Corp', 'PART-123', 10, 'high', 'released',
 CURRENT_TIMESTAMP + INTERVAL '7 days', CURRENT_TIMESTAMP);

-- Insert tasks for the job (first 10 operations)
INSERT INTO tasks (job_id, operation_id, sequence_in_job, status, planned_duration_minutes, planned_setup_minutes)
SELECT
    1, -- job_id
    id, -- operation_id
    sequence_number, -- sequence_in_job
    CASE
        WHEN sequence_number = 1 THEN 'ready'::task_status
        ELSE 'pending'::task_status
    END,
    standard_duration_minutes,
    setup_duration_minutes
FROM operations
WHERE sequence_number <= 10;

-- Insert business calendar (sample working days)
INSERT INTO business_calendar (calendar_date, is_working_day, working_hours_start, working_hours_end)
SELECT
    date_series::date,
    EXTRACT(DOW FROM date_series) BETWEEN 1 AND 5, -- Monday to Friday
    '07:00:00'::time,
    '16:00:00'::time
FROM generate_series(
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '30 days',
    INTERVAL '1 day'
) AS date_series;

-- Mark a holiday
UPDATE business_calendar
SET is_working_day = false,
    holiday_name = 'Sample Holiday'
WHERE calendar_date = CURRENT_DATE + INTERVAL '14 days';

-- =====================================================
-- HELPER FUNCTIONS FOR SCHEDULING
-- =====================================================

-- Function to check operator availability at a specific time
CREATE OR REPLACE FUNCTION is_operator_available(
    p_operator_id BIGINT,
    p_start_time TIMESTAMP,
    p_end_time TIMESTAMP
) RETURNS BOOLEAN AS $$
DECLARE
    v_available BOOLEAN;
    v_date DATE;
    v_start_time TIME;
    v_end_time TIME;
    v_lunch_start TIME;
    v_lunch_end TIME;
BEGIN
    v_date := p_start_time::date;
    v_start_time := p_start_time::time;
    v_end_time := p_end_time::time;

    -- Check if working day
    SELECT is_working_day INTO v_available
    FROM business_calendar
    WHERE calendar_date = v_date;

    IF NOT v_available OR v_available IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check operator availability
    SELECT
        COALESCE(oa.is_available, TRUE),
        COALESCE(oa.lunch_start, o.lunch_start),
        COALESCE(oa.lunch_start, o.lunch_start) +
            INTERVAL '1 minute' * COALESCE(oa.lunch_duration_minutes, o.lunch_duration_minutes)
    INTO v_available, v_lunch_start, v_lunch_end
    FROM operators o
    LEFT JOIN operator_availability oa
        ON oa.operator_id = o.id AND oa.availability_date = v_date
    WHERE o.id = p_operator_id;

    IF NOT v_available THEN
        RETURN FALSE;
    END IF;

    -- Check for conflicts with existing assignments
    IF EXISTS (
        SELECT 1
        FROM task_operator_assignments toa
        WHERE toa.operator_id = p_operator_id
          AND toa.planned_start_time < p_end_time
          AND toa.planned_end_time > p_start_time
    ) THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to find next available slot for a machine
CREATE OR REPLACE FUNCTION find_next_available_slot(
    p_machine_id BIGINT,
    p_duration_minutes INTEGER,
    p_after_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) RETURNS TIMESTAMP AS $$
DECLARE
    v_slot_start TIMESTAMP;
    v_slot_end TIMESTAMP;
    v_found BOOLEAN := FALSE;
BEGIN
    v_slot_start := p_after_time;

    WHILE NOT v_found LOOP
        v_slot_end := v_slot_start + (p_duration_minutes || ' minutes')::INTERVAL;

        -- Check if slot conflicts with existing tasks
        IF NOT EXISTS (
            SELECT 1
            FROM tasks t
            WHERE t.assigned_machine_id = p_machine_id
              AND t.planned_start_time < v_slot_end
              AND t.planned_end_time > v_slot_start
        )
        -- Check if slot conflicts with maintenance
        AND NOT EXISTS (
            SELECT 1
            FROM machine_maintenance mm
            WHERE mm.machine_id = p_machine_id
              AND mm.planned_start_time < v_slot_end
              AND mm.planned_end_time > v_slot_start
        )
        -- Check if within working hours
        AND EXISTS (
            SELECT 1
            FROM business_calendar bc
            WHERE bc.calendar_date = v_slot_start::date
              AND bc.is_working_day = TRUE
              AND v_slot_start::time >= bc.working_hours_start
              AND v_slot_end::time <= bc.working_hours_end
        ) THEN
            v_found := TRUE;
        ELSE
            -- Move to next potential slot
            v_slot_start := v_slot_start + INTERVAL '15 minutes';
        END IF;
    END LOOP;

    RETURN v_slot_start;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- PERMISSIONS (adjust as needed)
-- =====================================================

-- Create roles
CREATE ROLE scheduler_read;
CREATE ROLE scheduler_write;
CREATE ROLE scheduler_admin;

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO scheduler_read;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO scheduler_read;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO scheduler_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO scheduler_write;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO scheduler_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO scheduler_admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO scheduler_admin;
