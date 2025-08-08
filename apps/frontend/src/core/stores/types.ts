// Store type definitions for Zustand stores
export interface StoreApi<T> {
  getState: () => T
  setState: (partial: T | Partial<T> | ((state: T) => T | Partial<T>), replace?: boolean) => void
  subscribe: (listener: (state: T, prevState: T) => void) => () => void
  destroy: () => void
}
