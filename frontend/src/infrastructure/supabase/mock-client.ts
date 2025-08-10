// Minimal mock Supabase client for development when NEXT_PUBLIC_ENABLE_MOCK_DATA=true
// Provides subset used by the app to avoid runtime crashes without a backend

type MockSelectResult<T = any> = { data: T[] | null; error: { message: string } | null }

function makeResult<T>(data: T[] | null = [], error: { message: string } | null = null): MockSelectResult<T> {
  return { data, error }
}

function createQueryBuilder() {
  const api = {
    select(_fields?: string) {
      return api
    },
    order(_col: string, _opts?: any) {
      return api
    },
    limit(_n: number) {
      return makeResult()
    },
    insert(_values: any) {
      return makeResult()
    },
    update(_values: any) {
      return makeResult()
    },
    delete() {
      return makeResult()
    },
  }
  return api
}

export function createMockSupabaseClient() {
  return {
    auth: {
      async getUser() {
        return { data: { user: null }, error: null }
      },
    },
    from(_table: string) {
      return createQueryBuilder()
    },
  }
}
