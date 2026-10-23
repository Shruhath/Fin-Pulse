import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // A frozen copy reads its recorded answers from ./snapshot at run time, which the file tracer cannot see.
  outputFileTracingIncludes: { "/**": ["./snapshot/**/*"] },
};

export default nextConfig;
