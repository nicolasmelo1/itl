import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  transpilePackages: ["@itl/design-system", "@itl/ui-catalog"],
};

export default nextConfig;
