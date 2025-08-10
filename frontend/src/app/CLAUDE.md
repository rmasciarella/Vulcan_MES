# App Directory - Next.js 15 App Router

## Claude Assistant Rules for App Directory

1. **ALWAYS use Server Components by default** - Only add 'use client' when interactivity is needed
2. **NEVER create new route files** - Edit existing page.tsx and layout.tsx files
3. **Handle manufacturing data loads** - Use direct database queries in Server Components
4. **Implement proper error handling** - Manufacturing errors affect production

## Essential Patterns

### Server Component Data Loading (Next.js 15)

```typescript
// ✅ Direct database access with async params/searchParams
export default async function SchedulingPage({
  params,
  searchParams
}: {
  params: Promise<{ facility: string }>
  searchParams: Promise<{ status?: string }>
}) {
  // Await params and searchParams in Next.js 15
  const { facility } = await params;
  const { status } = await searchParams;

  const jobs = await supabase
    .from('production_jobs')
    .select('*')
    .eq('facility_id', facility)
    .eq('status', status || 'pending')
    .order('priority', { ascending: false });

  return <JobTable jobs={jobs.data || []} />;
}
```

### Client Components (Only When Needed)

```typescript
// ✅ Client Component for interactivity
'use client';
export function InteractiveScheduler() {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Handle job scheduling drag & drop
  const handleJobDrop = (jobId: string, newTime: Date) => {
    // Optimistic update with TanStack Query
  };

  return (
    <ScheduleGrid
      onJobDrop={handleJobDrop}
      selectedJob={selectedJob}
    />
  );
}
```

### Error Handling (Manufacturing Critical)

```typescript
// ✅ App Router error.tsx for manufacturing errors
'use client';
export default function Error({ error, reset }: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="p-6 border-l-4 border-red-500 bg-red-50">
      <h2 className="text-xl font-semibold text-red-800">
        Production System Error
      </h2>
      <p className="text-red-600 mt-2">
        {error.message || 'Failed to load production data'}
      </p>
      <button
        onClick={reset}
        className="mt-4 px-4 py-2 bg-red-600 text-white rounded"
      >
        Retry Loading
      </button>
    </div>
  );
}
```

### Loading States (Manufacturing Data)

```typescript
// ✅ loading.tsx for manufacturing data
export default function Loading() {
  return (
    <div className="space-y-4">
      <div className="h-8 bg-gray-200 rounded animate-pulse" />
      <div className="grid grid-cols-3 gap-4">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-200 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );
}
```

### API Routes (Manufacturing Integrations)

```typescript
// ✅ api/solver/optimize/route.ts
export async function POST(request: Request) {
  try {
    const { jobs, resources, constraints } = await request.json()

    // Validate using Zod
    const validatedInput = optimizationSchema.parse({ jobs, resources, constraints })

    // Call OR-Tools solver
    const optimizedSchedule = await runSolverOptimization(validatedInput)

    return NextResponse.json({ schedule: optimizedSchedule })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: 'Invalid input data' }, { status: 400 })
    }

    console.error('Solver optimization failed:', error)
    return NextResponse.json({ error: 'Optimization failed' }, { status: 500 })
  }
}
```

### Middleware (Authentication Only)

```typescript
// ✅ middleware.ts - Keep authentication simple
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (pathname.startsWith('/dashboard')) {
    const token = request.cookies.get('supabase-auth-token')
    if (!token) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }
}
```

### Next.js 15 Async Headers/Cookies

```typescript
// ✅ Server Component with async cookies
import { cookies } from 'next/headers';

export default async function UserDashboard() {
  const cookieStore = await cookies();
  const userPref = cookieStore.get('manufacturing-preferences');

  // Use preferences for facility-specific settings
  const preferences = userPref ? JSON.parse(userPref.value) : {};

  return <Dashboard preferences={preferences} />;
}

// ✅ Server Action with async headers
import { headers } from 'next/headers';

async function trackManufacturingAction() {
  'use server';

  const headersList = await headers();
  const userAgent = headersList.get('user-agent');

  // Log action for audit trail
  await logUserAction({
    userAgent,
    action: 'schedule_modified',
    timestamp: new Date()
  });
}
```

---

**Critical**: App Router files control manufacturing dashboard routing. Always use Server Components for data loading, Client Components only for interactivity. Handle errors gracefully since manufacturing data is mission-critical.
