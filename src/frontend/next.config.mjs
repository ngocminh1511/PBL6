/** @type {import('next').NextConfig} */
const origin = (process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000').replace(/\/$/, '');
const nextConfig = {
  reactStrictMode: true,
  images: { unoptimized: true },
  experimental: { cpus: 2 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: origin + '/api/:path*' }];
  },
};
export default nextConfig;
