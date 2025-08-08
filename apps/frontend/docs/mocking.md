# Mocking and stubbing patterns

Principles
- Mock infrastructure at the boundary (Supabase client, network). Keep domain pure and unmocked.
- Prefer repository/use-case level fakes over mocking fetch/select chains in many tests.
- Avoid coupling tests to library internals. Assert business outcomes.

Common mocks
- Supabase client: provided in test/setup.ts global mock; override per-test with vi.mocked if needed.
- Date/time: use vi.setSystemTime for deterministic tests.
- React Query: prefer wrapping hooks in a test QueryClient with retries disabled for unit tests.

Factories
- src/test/factories provides makeJob/makeTask builders for domain entities. Extend per domain as needed.

Examples
```ts
import { makeJob } from '@/test/factories/jobFactory'

test('job can start when ready', () => {
  const job = makeJob()
  job.start()
  expect(job.getStatus().value).toBe('IN_PROGRESS')
})
```

Integration hooks
- When testing hooks, stub repository methods (e.g., jobRepository.list = vi.fn().mockResolvedValue([...])) rather than mocking Supabase directly.
