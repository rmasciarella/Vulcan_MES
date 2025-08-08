/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    typedRoutes: true,
    optimizePackageImports: ['lucide-react', '@tanstack/react-query', '@tanstack/react-virtual'],
  },
  modularizeImports: {
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{ kebabCase member }}',
      preventFullImport: true,
    },
    '@tanstack/react-query': {
      transform: '@tanstack/react-query/{{ member }}',
      preventFullImport: true,
    },
    '@tanstack/react-virtual': {
      transform: '@tanstack/react-virtual/{{ member }}',
      preventFullImport: true,
    },
  },
}

module.exports = nextConfig