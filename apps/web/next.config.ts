import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  transpilePackages: [
    "@jplearn/domain",
    "@jplearn/design-tokens",
    "@jplearn/cms-schema",
  ],
};

export default nextConfig;
