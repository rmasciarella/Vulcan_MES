import type { NextConfig } from 'next'

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env['ANALYZE'] === 'true',
})

const nextConfig: NextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  outputFileTracing: true,
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
  eslint: {
    // Warning: This allows production builds to successfully complete even if
    // your project has ESLint errors.
    ignoreDuringBuilds: true,
  },
  experimental: {
    // Enable type checking in development
    typedRoutes: true,
    // Optimize package imports for better tree-shaking
    optimizePackageImports: ['lucide-react', '@tanstack/react-query', '@tanstack/react-virtual'],
  },
  modularizeImports: {
    // Optimize lucide-react imports to prevent bundling entire icon library
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{ kebabCase member }}',
      preventFullImport: true,
    },
    // Optimize TanStack Query imports for better tree-shaking
    '@tanstack/react-query': {
      transform: '@tanstack/react-query/{{ member }}',
      preventFullImport: true,
    },
    // Optimize TanStack Virtual imports if used
    '@tanstack/react-virtual': {
      transform: '@tanstack/react-virtual/{{ member }}',
      preventFullImport: true,
    },
  },
  transpilePackages: ['@vulcan/domain', '@vulcan/*'],
  webpack: (config: any, { dev, isServer, webpack }: any) => {
    // Optionally export webpack stats when EXPORT_STATS=true
    if (!dev && process.env['EXPORT_STATS'] === 'true') {
      class WriteStatsPlugin {
        apply(compiler: any) {
          compiler.hooks.done.tap('WriteStatsPlugin', (stats: any) => {
            try {
              const fs = require('fs')
              const path = require('path')
              const outPath = path.join(process.cwd(), '.next', 'webpack-stats.json')
              const json = stats.toJson({ all: true })
              fs.mkdirSync(path.dirname(outPath), { recursive: true })
              fs.writeFileSync(outPath, JSON.stringify(json, null, 2))
            } catch (e) {
              // no-op
            }
          })
        }
      }
      config.plugins = config.plugins || []
      config.plugins.push(new WriteStatsPlugin())
    }
    return config
  },
}

export default withBundleAnalyzer(nextConfig)
