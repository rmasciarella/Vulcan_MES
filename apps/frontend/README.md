# Frontend performance and bundle budgets

This project enforces a first‑load JS budget for the dashboard to prevent regressions.

What’s included
- Next.js optimizations: swcMinify, outputFileTracing, modularizeImports, optimizePackageImports
- Transpile packages for better tree‑shaking: @vulcan/*
- Bundle analyzer: ANALYZE=true pnpm build
- CI bundle size check for /(dashboard)/planning with a 220 kB gzipped budget

Local analysis
1) Build with stats
   EXPORT_STATS=true pnpm build
2) Run the bundle check
   pnpm check-bundle

Config
- Script: apps/frontend/scripts/check-bundle-size.js
- Env overrides:
  - BUNDLE_ROUTE: route segment to evaluate (default: /(dashboard)/planning)
  - BUNDLE_BUDGET_KB: budget in kB (default: 220)

Dynamic imports
- @tanstack/react-query-devtools is dynamically imported and disabled on the server
- VirtualizedTable is dynamically imported (client‑only) to reduce initial JS

Bundle analyzer
- To visualize bundles:
  ANALYZE=true pnpm build
  Then open .next/analyze in your browser (the analyzer plugin will output a report)

Notes
- The stats file is emitted when EXPORT_STATS=true; CI sets this automatically.
- Keep UX identical and preserve existing RSC boundaries; dynamic imports only applied to client‑only utilities.

