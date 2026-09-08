import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig = (phase: string): NextConfig => ({
  // Keep production builds from replacing chunks used by a running dev server.
  distDir: process.env.NEXT_DIST_DIR || (phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next"),
  transpilePackages: [
    "@jplearn/domain",
    "@jplearn/design-tokens",
    "@jplearn/cms-schema",
  ],
});

export default nextConfig;
