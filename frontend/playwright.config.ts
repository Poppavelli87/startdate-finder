import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120000,
  expect: {
    timeout: 10000
  },
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      timeout: 120000,
      reuseExistingServer: true,
      env: {
        STARTDATE_TEST_MODE: "1",
        FEATURE_SOCIAL_HINTS: "1"
      }
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      cwd: ".",
      url: "http://127.0.0.1:5173",
      timeout: 120000,
      reuseExistingServer: true,
      env: {
        VITE_API_PROXY_TARGET: "http://127.0.0.1:8000"
      }
    }
  ]
});

