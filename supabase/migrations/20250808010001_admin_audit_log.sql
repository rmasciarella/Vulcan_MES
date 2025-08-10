-- Migration: Admin Audit Log + Natural Key Constraints
-- Purpose: Create audit logging infrastructure and add unique constraints on natural keys
-- Date: 2025-08-08

-- 1) Create admin_audit_log table
create table if not exists public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid, -- referencing auth.users (not enforced to allow system writes)
  action_type text not null check (action_type in (
    'INSERT','UPDATE','DELETE','UPSERT','BULK_IMPORT','BULK_UPDATE','BULK_DELETE','RLS_BYPASS','OTHER'
  )),
  table_name text not null,
  row_ids text[] not null, -- array of primary key values (as text) for impacted rows
  changes_json jsonb not null default '{}'::jsonb, -- { before: {}, after: {}, diff: {} }
  "timestamp" timestamptz not null default now(),
  ip_address inet,
  user_agent text
);

comment on table public.admin_audit_log is 'Administrative audit log for manual data changes and privileged actions. Readable only by admins.';
comment on column public.admin_audit_log.user_id is 'User who performed the action (auth.users.id). May be null for system actions.';
comment on column public.admin_audit_log.table_name is 'Target table affected by the action.';
comment on column public.admin_audit_log.row_ids is 'Primary key(s) of affected rows (stored as text for generality).';
comment on column public.admin_audit_log.changes_json is 'JSON payload with before/after/diff of changes when available.';
comment on column public.admin_audit_log."timestamp" is 'When the action occurred.';

-- Optional FK (commented to avoid coupling); uncomment if you want strict FK
-- alter table public.admin_audit_log
--   add constraint admin_audit_log_user_fk
--   foreign key (user_id) references auth.users(id) on delete set null;

-- Indexes for common queries
create index if not exists idx_admin_audit_log_user_id on public.admin_audit_log(user_id);
create index if not exists idx_admin_audit_log_table_name on public.admin_audit_log(table_name);
create index if not exists idx_admin_audit_log_timestamp on public.admin_audit_log("timestamp" desc);

-- Enable RLS and restrict read to admins only
alter table public.admin_audit_log enable row level security;

-- Helper: detect admin via JWT custom claims
create or replace function public.is_admin()
returns boolean
language sql
stable
as $$
  -- Accept either role='admin' or is_admin=true in JWT claims
  select coalesce((auth.jwt() ->> 'role') = 'admin', false)
      or coalesce((auth.jwt() ->> 'is_admin')::boolean, false);
$$;

-- Policy: Only admins can select
create policy if not exists "admin_audit_read_admins_only"
  on public.admin_audit_log
  for select
  to authenticated
  using (public.is_admin());

-- No insert/update/delete policies are defined intentionally; service_role bypasses RLS for server-side writes.

-- 2) Natural key alignment: add safe unique indexes (serve as constraints)
-- Work Orders -> job_instances.name assumed to be the natural business key
create unique index if not exists ux_job_instances_name on public.job_instances(name);

-- Work Cells -> workcells.name should be unique
create unique index if not exists ux_workcells_name on public.workcells(name);

-- Machines -> combination of (name, workcell_id) should be unique within a cell
create unique index if not exists ux_machines_name_workcell on public.machines(name, workcell_id);

-- Departments -> name unique
create unique index if not exists ux_departments_name on public.departments(name);

-- Operators -> employee_id already unique per existing schema (no action)

-- Calendars/Skills: not present as standalone tables in current schema; see docs for guidance.

