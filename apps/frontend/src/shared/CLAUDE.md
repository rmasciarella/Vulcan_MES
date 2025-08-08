# Shared - Reusable UI and Utilities

## Claude Assistant Rules for Shared Layer

1. **NO business logic** - Only generic UI components and utilities
2. **NO manufacturing domain knowledge** - Keep components generic and composable
3. **Virtualization for large lists** - Use react-window for >100 items
4. **shadcn/ui patterns** - Follow established component patterns
5. **Performance first** - Optimize for manufacturing data volumes

## Essential Patterns

### Data Table with Virtualization

```typescript
// ✅ High-performance table for manufacturing data
export function DataTable<TData>({
  columns,
  data,
  loading = false,
  enableVirtualization = false,
  maxHeight = 600
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (loading) return <DataTableSkeleton />;

  // ✅ Use virtualization for large datasets
  if (enableVirtualization && data.length > 100) {
    return <VirtualizedTable table={table} maxHeight={maxHeight} />;
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

### Reusable Hooks

```typescript
// ✅ useDebounce for search inputs
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

// ✅ usePagination for large datasets
export function usePagination({ totalItems, itemsPerPage, initialPage = 1 }) {
  const [currentPage, setCurrentPage] = useState(initialPage)

  const paginationData = useMemo(() => {
    const totalPages = Math.ceil(totalItems / itemsPerPage)
    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = Math.min(startIndex + itemsPerPage, totalItems)

    return {
      currentPage,
      totalPages,
      startIndex,
      endIndex,
      hasNextPage: currentPage < totalPages,
      hasPrevPage: currentPage > 1,
    }
  }, [currentPage, totalItems, itemsPerPage])

  return {
    ...paginationData,
    goToPage: (page: number) =>
      setCurrentPage(Math.max(1, Math.min(page, paginationData.totalPages))),
    nextPage: () => paginationData.hasNextPage && setCurrentPage((current) => current + 1),
    prevPage: () => paginationData.hasPrevPage && setCurrentPage((current) => current - 1),
  }
}
```

### Utility Functions

```typescript
// ✅ Common utilities (NO manufacturing domain logic)
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function generateId(): string {
  return Math.random().toString(36).substring(2) + Date.now().toString(36)
}

export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json)
  } catch {
    return fallback
  }
}

export function groupBy<T, K extends string | number>(
  array: T[],
  keyFn: (item: T) => K,
): Record<K, T[]> {
  return array.reduce(
    (groups, item) => {
      const key = keyFn(item)
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
      return groups
    },
    {} as Record<K, T[]>,
  )
}
```

### Validation Schemas (Common patterns only)

```typescript
// ✅ Common validation schemas with Zod
export const commonSchemas = {
  email: z.string().email('Invalid email address'),
  positiveNumber: z.number().positive('Must be a positive number'),
  nonEmptyString: z.string().min(1, 'This field is required'),
  dateString: z.string().refine((date) => !isNaN(Date.parse(date)), 'Invalid date format'),
  duration: z.number().min(1, 'Duration must be at least 1 minute'),
  priority: z.enum(['low', 'medium', 'high', 'urgent']),
}

// ✅ Shared types (NO manufacturing domain knowledge)
export interface PaginationParams {
  page: number
  limit: number
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  totalPages: number
}

export interface ApiResponse<T = any> {
  data: T
  message?: string
  success: boolean
}
```

---

**Critical**: Shared layer contains NO business logic - only generic UI components, utilities, and types. Use virtualization for large datasets. Keep components framework-agnostic when possible.
