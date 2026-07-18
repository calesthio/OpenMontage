import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for web/Dockerfile's multi-stage build — it copies
  // .next/standalone into the runner image, which `next build` only emits
  // with this flag set. Without it, `docker build` fails at that COPY step.
  output: "standalone",
};

export default nextConfig;
