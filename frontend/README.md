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

---

## Deployment & Monitoring (Netlify + Sentry)

This section is a step‑by‑step runbook to deploy this Next.js app to Netlify and verify production health. You can follow it even if you don’t have production URLs yet; Netlify will give you one after the first deploy.

Prereqs
- A GitHub/GitLab/Bitbucket repo for this app (this folder is apps/frontend)
- Netlify account
- Optional: Sentry account (for error tracking)

1) Connect the repo to Netlify
- In Netlify UI, New site from Git → pick your repo
- Base directory: apps/frontend (since this app lives here)
- Build command: npm run build
- Publish directory: .next
- Add the Next.js plugin: @netlify/plugin-nextjs (already configured in netlify.toml)
- Environment variables (set in Netlify UI, no secrets in git):
  - NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  - NEXT_PUBLIC_APP_ENV=production
  - Optional: NEXT_PUBLIC_API_URL if calling an external API

Note on netlify.toml
- This file is already in apps/frontend and is configured with base="." so it will work when the site’s base directory in Netlify is set to apps/frontend.

2) First deploy (push to main)
- Ensure your main branch is up to date
- git push origin main
- Netlify will build and deploy; you’ll get a production URL like https://your-site.netlify.app

3) Optional: API routing to avoid CORS
- If your API is hosted elsewhere, you can route through Netlify so the browser hits /api/* and Netlify proxies to your API (no CORS needed).
- Edit netlify.toml → [[redirects]] block:
  - from = "/api/*"
  - to = "https://your-backend-url.com/api/:splat" (replace with your API origin)
  - status = 200, force = true
- Commit, push to main, and redeploy.

4) Verify SSR/SSG in production
- Pick a page expected to be server-rendered (e.g., a route under /(dashboard) that fetches on the server).
- Use curl to inspect output HTML (should not be a client-side shell only):
  curl -s https://your-site.netlify.app/ | head -n 50
- Look for meaningful HTML and content, not just a blank root div. Dynamic client islands are fine.
- Cache behavior: SSG pages usually emit Cache-Control with a max-age. SSR pages may be private/no-store or short-lived.

5) Verify CORS headers
- If you call an external API directly from the browser:
  - Open DevTools → Network → XHR/fetch → pick an API call
  - Check response headers include: Access-Control-Allow-Origin matching your site, Access-Control-Allow-Credentials if using cookies, Access-Control-Allow-Headers for content-type, authorization
- If you proxy through /api via Netlify, CORS is bypassed (browser sees same-origin).

6) Test API endpoints from the production frontend
- If using the proxy: in the browser, open the app and exercise flows that hit /api/*
- Or use curl directly against the API (replace placeholders):
  curl -s -H "Authorization: Bearer {{TOKEN}}" https://api.example.com/v1/health
  curl -s -X POST -H "Content-Type: application/json" -d '{"ping":true}' https://api.example.com/v1/ping
- For Supabase edges (if applicable), verify anon key is public and NOT the service role key.

7) Enable Netlify Analytics (optional, paid)
- Netlify UI → Site settings → Analytics → Enable
- After traffic, check:
  - Pageviews, unique visitors
  - Top pages, slow pages
  - Response status distribution

8) Configure Sentry error tracking (optional)
- Install: pnpm add @sentry/nextjs
- Initialize (Next 15):
  - Create sentry.client.config.ts and sentry.server.config.ts in this folder with your DSN and environment
  - Minimal example:
    // sentry.client.config.ts
    import * as Sentry from '@sentry/nextjs'
    Sentry.init({ dsn: process.env.NEXT_PUBLIC_SENTRY_DSN, tracesSampleRate: 1.0 })

    // sentry.server.config.ts
    import * as Sentry from '@sentry/nextjs'
    Sentry.init({ dsn: process.env.SENTRY_DSN, tracesSampleRate: 0.2 })
  - Add env vars in Netlify UI:
    - NEXT_PUBLIC_SENTRY_DSN (public)
    - SENTRY_DSN (server-only)
- Optional: wrap route handlers or add error boundaries for better reporting.

9) Production smoke test (once you have a URL)
- Run scripts/smoke-prod.sh with SITE_URL set:
  SITE_URL=https://your-site.netlify.app bash scripts/smoke-prod.sh
- It will hit the home page, check a known route, and (optionally) an API health endpoint.

10) Runbook for incidents
- Check Netlify Deploys → latest build logs
- Check Netlify Functions logs (if you add them later)
- Check Sentry issues
- Roll back: Netlify → Deploys → Promote a previous successful deploy

FAQ
- Do I need CORS config? Only if your browser calls a different origin. Prefer the /api proxy to avoid CORS headaches.
- Where do I put secrets? Netlify environment variables. Do not commit secrets to git.
- How do I add custom headers? Use [[headers]] in netlify.toml for static assets; API headers should come from your API origin.

