import nextConstants from 'next/constants.js';

const origin = (process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000').replace(/\/$/, '');
/** @param {string} phase @returns {import('next').NextConfig} */
const nextConfig = (phase) => ({
  // Dev and production builds can run together without overwriting chunks.
  distDir: phase === nextConstants.PHASE_DEVELOPMENT_SERVER ? '.next-dev' : '.next',
  reactStrictMode: true,
  images: { unoptimized: true },
  experimental: { cpus: 2 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: origin + '/api/:path*' }];
  },
});
export default nextConfig;
