-- Create domain_events table for event sourcing and event store
-- This table stores all domain events for audit trail and event replay

create table if not exists public.domain_events (
  id uuid default gen_random_uuid() primary key,
  aggregate_id text not null,
  aggregate_type text not null,
  event_type text not null,
  event_data jsonb not null,
  event_metadata jsonb default '{}'::jsonb,
  version integer not null,
  occurred_at timestamptz default now() not null,
  created_at timestamptz default now() not null,
  
  -- Unique constraint to prevent duplicate events for same aggregate + version
  unique(aggregate_id, aggregate_type, version)
);

-- Indexes for performance
create index if not exists idx_domain_events_aggregate 
  on public.domain_events (aggregate_id, aggregate_type);

create index if not exists idx_domain_events_type 
  on public.domain_events (event_type);

create index if not exists idx_domain_events_occurred_at 
  on public.domain_events (occurred_at desc);

create index if not exists idx_domain_events_aggregate_version 
  on public.domain_events (aggregate_id, aggregate_type, version);

-- Enable RLS
alter table public.domain_events enable row level security;

-- Create basic RLS policy (will be refined when authentication is implemented)
create policy "Enable read access for all users" on public.domain_events
  for select using (true);

create policy "Enable insert access for all users" on public.domain_events
  for insert with check (true);

-- Create function to get events for an aggregate
create or replace function public.get_domain_events_for_aggregate(
  p_aggregate_id text,
  p_aggregate_type text,
  p_from_version integer default 0
)
returns table(
  id uuid,
  aggregate_id text,
  aggregate_type text,
  event_type text,
  event_data jsonb,
  event_metadata jsonb,
  version integer,
  occurred_at timestamptz
)
language plpgsql
security definer
as $$
begin
  return query
    select 
      de.id,
      de.aggregate_id,
      de.aggregate_type,
      de.event_type,
      de.event_data,
      de.event_metadata,
      de.version,
      de.occurred_at
    from public.domain_events de
    where de.aggregate_id = p_aggregate_id
      and de.aggregate_type = p_aggregate_type
      and de.version > p_from_version
    order by de.version asc;
end;
$$;

-- Create function to get latest events across all aggregates
create or replace function public.get_recent_domain_events(
  p_limit integer default 100,
  p_event_types text[] default null
)
returns table(
  id uuid,
  aggregate_id text,
  aggregate_type text,
  event_type text,
  event_data jsonb,
  event_metadata jsonb,
  version integer,
  occurred_at timestamptz
)
language plpgsql
security definer
as $$
begin
  return query
    select 
      de.id,
      de.aggregate_id,
      de.aggregate_type,
      de.event_type,
      de.event_data,
      de.event_metadata,
      de.version,
      de.occurred_at
    from public.domain_events de
    where (p_event_types is null or de.event_type = any(p_event_types))
    order by de.occurred_at desc
    limit p_limit;
end;
$$;

-- Create function to count events by type
create or replace function public.get_domain_event_stats()
returns table(
  event_type text,
  aggregate_type text,
  event_count bigint,
  latest_event timestamptz
)
language plpgsql
security definer
as $$
begin
  return query
    select 
      de.event_type,
      de.aggregate_type,
      count(*) as event_count,
      max(de.occurred_at) as latest_event
    from public.domain_events de
    group by de.event_type, de.aggregate_type
    order by event_count desc;
end;
$$;

-- Grant appropriate permissions
grant select, insert on public.domain_events to anon, authenticated;
grant execute on function public.get_domain_events_for_aggregate(text, text, integer) to anon, authenticated;
grant execute on function public.get_recent_domain_events(integer, text[]) to anon, authenticated;
grant execute on function public.get_domain_event_stats() to anon, authenticated;