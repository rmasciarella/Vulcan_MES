-- Migration to support DDD patterns: Event Store and Optimistic Concurrency
-- This migration adds the infrastructure needed for:
-- 1. Domain event persistence and audit compliance
-- 2. Optimistic concurrency control with version tracking
-- 3. Event sourcing capabilities for manufacturing traceability

-- Add version column to existing aggregate tables for optimistic concurrency control
ALTER TABLE job_instances 
ADD COLUMN version INTEGER DEFAULT 1 NOT NULL;

-- Create index on version column for efficient queries
CREATE INDEX idx_job_instances_version ON job_instances(version);

-- Create domain_events table for event store implementation
CREATE TABLE domain_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    event_metadata JSONB DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create indices for efficient event store queries
CREATE INDEX idx_domain_events_aggregate_id ON domain_events(aggregate_id);
CREATE INDEX idx_domain_events_aggregate_type ON domain_events(aggregate_type);
CREATE INDEX idx_domain_events_event_type ON domain_events(event_type);
CREATE INDEX idx_domain_events_occurred_at ON domain_events(occurred_at);
CREATE INDEX idx_domain_events_aggregate_version ON domain_events(aggregate_id, version);

-- Create composite index for event sourcing queries
CREATE INDEX idx_domain_events_sourcing ON domain_events(aggregate_id, version ASC);

-- Add constraint to ensure version is positive
ALTER TABLE domain_events 
ADD CONSTRAINT chk_domain_events_version_positive 
CHECK (version > 0);

-- Add constraint to ensure aggregate_id is not empty
ALTER TABLE domain_events 
ADD CONSTRAINT chk_domain_events_aggregate_id_not_empty 
CHECK (LENGTH(TRIM(aggregate_id)) > 0);

-- Add constraint to ensure event_type is not empty
ALTER TABLE domain_events 
ADD CONSTRAINT chk_domain_events_event_type_not_empty 
CHECK (LENGTH(TRIM(event_type)) > 0);

-- Add RLS (Row Level Security) policies for domain events
ALTER TABLE domain_events ENABLE ROW LEVEL SECURITY;

-- Policy to allow authenticated users to read domain events
CREATE POLICY "Allow authenticated users to read domain events"
ON domain_events FOR SELECT
TO authenticated
USING (true);

-- Policy to allow authenticated users to insert domain events
CREATE POLICY "Allow authenticated users to insert domain events"
ON domain_events FOR INSERT
TO authenticated
WITH CHECK (true);

-- Create a function to automatically update version on job updates
CREATE OR REPLACE FUNCTION increment_job_version()
RETURNS TRIGGER AS $$
BEGIN
    -- Only increment version on actual data changes, not metadata updates
    IF (OLD.name, OLD.description, OLD.template_id, OLD.due_date, OLD.earliest_start_date, OLD.status) IS DISTINCT FROM 
       (NEW.name, NEW.description, NEW.template_id, NEW.due_date, NEW.earliest_start_date, NEW.status) THEN
        NEW.version = COALESCE(OLD.version, 1) + 1;
        NEW.updated_at = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically increment job version
CREATE TRIGGER trigger_increment_job_version
    BEFORE UPDATE ON job_instances
    FOR EACH ROW
    EXECUTE FUNCTION increment_job_version();

-- Add comment explaining the DDD patterns implementation
COMMENT ON TABLE domain_events IS 'Event store for Domain-Driven Design patterns. Stores all domain events for audit trails, event sourcing, and cross-domain integration. Critical for manufacturing compliance and traceability requirements.';

COMMENT ON COLUMN domain_events.aggregate_id IS 'Unique identifier of the aggregate that produced this event';
COMMENT ON COLUMN domain_events.aggregate_type IS 'Type of aggregate (Job, Task, Resource, etc.)';
COMMENT ON COLUMN domain_events.event_type IS 'Type of domain event (JobCreated, JobStatusChanged, etc.)';
COMMENT ON COLUMN domain_events.event_data IS 'Event payload containing all relevant data for the event';
COMMENT ON COLUMN domain_events.event_metadata IS 'Additional metadata like correlation IDs, causation IDs, user context';
COMMENT ON COLUMN domain_events.version IS 'Version of the aggregate when this event occurred (for event sourcing)';
COMMENT ON COLUMN domain_events.occurred_at IS 'When the domain event actually occurred (business time)';
COMMENT ON COLUMN domain_events.created_at IS 'When the event was persisted to the event store (system time)';

COMMENT ON COLUMN job_instances.version IS 'Version number for optimistic concurrency control. Automatically incremented on updates.';

-- Create a view for easy event history queries
CREATE VIEW event_history AS
SELECT 
    de.id,
    de.aggregate_id,
    de.aggregate_type,
    de.event_type,
    de.event_data,
    de.event_metadata,
    de.version,
    de.occurred_at,
    de.created_at,
    -- Add human-readable event description
    CASE 
        WHEN de.event_type = 'JobCreated' THEN 'Job created: ' || COALESCE(de.event_data->>'serialNumber', 'Unknown')
        WHEN de.event_type = 'JobStatusChanged' THEN 'Status changed from ' || COALESCE(de.event_data->>'previousStatus', 'Unknown') || ' to ' || COALESCE(de.event_data->>'newStatus', 'Unknown')
        ELSE de.event_type
    END as event_description
FROM domain_events de
ORDER BY de.occurred_at DESC;

COMMENT ON VIEW event_history IS 'Manufacturing event history view with human-readable descriptions for audit and compliance reporting.';