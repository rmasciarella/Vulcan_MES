/*
  Bundle size check script for Next.js app (apps/frontend)
  - Reads .next/webpack-stats.json (emitted when EXPORT_STATS=true)
  - Computes gzipped size of first-load JS for a target route
  - Fails if size exceeds configured budget

  Usage:
    EXPORT_STATS=true pnpm build && node scripts/check-bundle-size.js

  Environment variables:
    BUNDLE_ROUTE: route segment to check (default: "/(dashboard)/planning")
    BUNDLE_BUDGET_KB: integer kilobytes budget (default: 220)

  Notes:
  - This script parses Webpack stats, then resolves emitted JS chunks in .next/static and measures gzip sizes.
  - It approximates Next first-load by including route chunks + shared runtime chunks for the route.
  - Keep ANALYZE=true available via next.config.ts.
*/

const fs = require('fs')
const path = require('path')
const zlib = require('zlib')

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'))
}

function gzipSize(buffer) {
  return zlib.gzipSync(buffer).length
}

function formatKB(bytes) {
  return Math.round((bytes / 1024) * 10) / 10
}

function findRouteAssets(stats, route) {
  // Gather assets from chunks whose names include the route path segment
  // Next 15+ chunk names usually include route path and other shared names
  const allAssets = new Set()
  const routeFragment = route.replace(/^\//, '') // strip leading slash

  const chunks = stats?.chunks || []
  for (const chunk of chunks) {
    const names = chunk?.names || []
    const hasRouteName = names.some((n) => typeof n === 'string' && n.includes(routeFragment))
    if (!hasRouteName) continue
    for (const file of chunk.files || []) {
      if (typeof file === 'string' && file.endsWith('.js')) allAssets.add(file)
    }
    // Include auxiliary chunk files
    for (const aux of chunk.auxiliaryFiles || []) {
      if (typeof aux === 'string' && aux.endsWith('.js')) allAssets.add(aux)
    }
  }

  // Include common/runtime chunks that are initial and JS
  for (const asset of stats?.assets || []) {
    const name = asset?.name || ''
    if (name.endsWith('.js') && /(^|\/)static\/(chunks|runtime)\//.test(name)) {
      if (asset.info?.initial) {
        allAssets.add(name)
      }
    }
  }

  return Array.from(allAssets)
}

function resolveAssetPath(assetName) {
  // Assets are emitted under .next/; assets names are usually relative to .next/
  return path.join(process.cwd(), '.next', assetName)
}

function main() {
  const route = process.env.BUNDLE_ROUTE || '/(dashboard)/planning'
  const budgetKB = parseInt(process.env.BUNDLE_BUDGET_KB || '220', 10)

  const statsPath = path.join(process.cwd(), '.next', 'webpack-stats.json')
  if (!fs.existsSync(statsPath)) {
    console.error('Missing .next/webpack-stats.json. Build with EXPORT_STATS=true to generate it.')
    process.exit(2)
  }

  const stats = readJson(statsPath)
  const assets = findRouteAssets(stats, route)
  if (!assets.length) {
    console.warn(`No JS assets matched for route ${route}. Check route naming or stats content.`)
  }

  let totalGzip = 0
  const details = []
  for (const a of assets) {
    const abs = resolveAssetPath(a)
    if (!fs.existsSync(abs)) continue
    const buf = fs.readFileSync(abs)
    const gz = gzipSize(buf)
    totalGzip += gz
    details.push({ asset: a, gzipKB: formatKB(gz) })
  }

  console.log('Bundle size report (gzipped):')
  console.table(details)
  const totalKB = formatKB(totalGzip)
  console.log(`Route: ${route}`)
  console.log(`Total first-load JS (approx): ${totalKB} kB (budget ${budgetKB} kB)`) 

  if (totalKB > budgetKB) {
    console.error(`Bundle size budget exceeded for ${route}: ${totalKB} kB > ${budgetKB} kB`)
    process.exit(1)
  } else {
    console.log('Bundle size within budget ✅')
  }
}

main()

