# Testing strategy per domain (Frontend)

This app follows DDD boundaries. Tests are organized to validate behavior closest to the domain while minimizing brittle UI assertions.

Layers and goals:
- Unit (95%+ coverage enforced via Vitest):
  - Value objects and entities in packages/domain or core/domains
  - Pure utilities in src/shared/lib
- Integration:
  - Feature hooks using repositories/use-cases (no direct Supabase calls). Prefer mocking repositories.
  - Cross-domain invariants (e.g., jobs ↔ tasks, resources capacity)
- End-to-End (Playwright):
  - Critical user paths: auth/login, planning view load, job create/edit, task flow
  - Runs against Next dev server via Playwright webServer

Domain mapping and example tests:
- Scheduling: validate job/task sequencing, mode selection, capacity constraints
- Work Orders: job lifecycle transitions and invariants
- Resources: work cell capacity, machine availability windows
- Calendars: business hours, blackout dates (when implemented)
- Skills: skill hierarchy and fulfillment rules
- Work Cells: capacity and events

DDD-alignment rules for tests:
- Do: test behavior through domain entities/use-cases. Mock infrastructure (Supabase) at boundaries.
- Do not: test by poking tables or bypassing repositories from UI tests.
- Remove tests that assert implementation details of infrastructure or perform ad-hoc DB calls from UI code.

Commands:
- Unit/Integration: pnpm -w --filter @vulcan/frontend run test:coverage
- E2E: pnpm -w --filter @vulcan/frontend run test:e2e

Coverage policy:
- Configured at 95% for lines, branches, functions, statements. See vitest.config.ts. Exceptions require justification and per-file threshold overrides.
