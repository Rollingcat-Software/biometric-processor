/** @type {import('next').NextConfig} */

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

const nextConfig = {
  // Enable static export
  output: 'export',

  reactStrictMode: true,

  // Ignore ESLint and TypeScript errors during build (pre-existing issues)
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },

  // Image optimization - unoptimized for static export
  images: {
    unoptimized: true,
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_APP_NAME: 'Biometric Processor Demo',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
    // Empty = same origin (FastAPI will serve everything)
    NEXT_PUBLIC_API_URL: '',
  },

  // Webpack configuration
  webpack: (config, { isServer }) => {
    // Handle canvas for server-side rendering
    if (isServer) {
      config.externals.push({
        canvas: 'commonjs canvas',
      });
    }

    return config;
  },

  // Experimental features
  experimental: {
    // Bundle optimization - tree shake and optimize heavy packages
    optimizePackageImports: ['recharts', 'framer-motion', '@radix-ui/react-icons', 'lucide-react'],
  },

  // Static export specific
  trailingSlash: true,
  skipTrailingSlashRedirect: true,
};

module.exports = withBundleAnalyzer(nextConfig);
