import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false, // Prevents duplicate WS mount on dev
  async rewrites() {
    return [
      {
        source: "/api/trading/:path*",
        destination: "http://127.0.0.1:8001/api/trading/:path*",
      },
      {
        source: "/api/sports/:path*",
        destination: "http://127.0.0.1:8001/api/sports/:path*",
      },
    ];
  },
};

export default nextConfig;
