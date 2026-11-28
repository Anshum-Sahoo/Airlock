/** @type {import('next').NextConfig} */
const nextConfig = {
  // Public API base URL only. Never put NVIDIA credentials or backend secrets here.
  // NEXT_PUBLIC_AIRLOCK_API_URL is the backend base; default to localhost for local dev.
  // The reviewer token is NEVER in env — it is entered in the UI at runtime.
  env: {},
};

module.exports = nextConfig;
