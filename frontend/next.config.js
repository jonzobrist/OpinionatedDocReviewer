function splitCsv(value) {
  if (!value) return [];
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, '');
}

const rewriteApiBase = trimTrailingSlash(
  process.env.NEXT_SERVER_API_BASE ||
    process.env.NEXT_PUBLIC_API_BASE ||
    'http://localhost:8006/api'
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  allowedDevOrigins: splitCsv(process.env.ALLOWED_DEV_ORIGINS),
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${rewriteApiBase}/:path*`
      }
    ];
  }
};

module.exports = nextConfig;
