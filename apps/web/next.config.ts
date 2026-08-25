import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: [
    "@jplearn/domain",
    "@jplearn/design-tokens",
    "@jplearn/cms-schema",
  ],
};

export default nextConfig;
