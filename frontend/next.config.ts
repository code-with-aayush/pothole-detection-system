import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @ts-expect-error - disable automatic generation of AGENTS.md and CLAUDE.md by Next.js dev server
  agentRules: false,
};

export default nextConfig;
