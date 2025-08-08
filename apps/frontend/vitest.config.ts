import { defineConfig } from 'vitest/config'
import path from 'node:path'

export default defineConfig({
  resolve: {
    alias: {
      // Internal path aliases
      '@/*': path.resolve(__dirname, 'src/*'),
      '@/types/*': path.resolve(__dirname, 'types/*'),
      '@/core/*': path.resolve(__dirname, 'src/core/*'),
      
      // Workspace dependencies - @vulcan/domain package  
      '@vulcan/domain': path.resolve(__dirname, '../../packages/domain/src/index.ts'),
      '@vulcan/domain/jobs': path.resolve(__dirname, '../../packages/domain/src/jobs/index.ts'),
      '@vulcan/domain/tasks': path.resolve(__dirname, '../../packages/domain/src/tasks/index.ts'),
      '@vulcan/domain/resources': path.resolve(__dirname, '../../packages/domain/src/resources/index.ts'),
      '@vulcan/domain/testing': path.resolve(__dirname, '../../packages/domain/src/testing/index.ts'),
      '@vulcan/domain/*': path.resolve(__dirname, '../../packages/domain/src/*'),
      
      // Local frontend domain implementation aliases
      '@/core/domains/jobs': path.resolve(__dirname, 'src/core/domains/jobs.ts'),
      '@/core/domains/tasks': path.resolve(__dirname, 'src/core/domains/tasks.ts'),
      '@/core/domains/*': path.resolve(__dirname, 'src/core/domains/*'),
      
      // Test stubs for missing modules
      '@/core/use-cases/use-case-factory': path.resolve(__dirname, 'test/stubs/use-case-factory.ts'),
      '@/core/stores/ui-store': path.resolve(__dirname, 'test/stubs/ui-store.ts'),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}', 'src/**/__tests__/**/*.{ts,tsx}'],
    setupFiles: ['test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './coverage',
      all: true,
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/CLAUDE.md',
        'src/**/examples/**',
        'src/**/__tests__/**',
        'src/**/test/**',
        '**/*.d.ts'
      ],
      thresholds: {
        lines: 95,
        functions: 95,
        branches: 95,
        statements: 95,
      },
    },
  },
})