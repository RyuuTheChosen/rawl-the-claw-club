/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@rawl/shared'],
  experimental: {},
  webpack: (config) => {
    // Fixes for wagmi/viem/WalletConnect SSR compatibility
    config.resolve.fallback = {
      ...config.resolve.fallback,
      'pino-pretty': false,
      encoding: false,
      '@react-native-async-storage/async-storage': false,
    };
    config.externals.push('pino-pretty', 'encoding');
    return config;
  },
};

export default nextConfig;
