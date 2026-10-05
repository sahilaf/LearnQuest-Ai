// End-to-end tests: a real browser against the real frontend and backend,
// on a fresh database, with outside AI services scripted. See TEST_PLAN.md.
import { defineConfig, devices } from '@playwright/test';

const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5180;
const python = process.platform === 'win32' ? 'python' : 'python3';

export default defineConfig({
  testDir: './tests',
  // One worker: every test shares one seeded database and one backend.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { outputFolder: 'reports/html', open: 'never' }]],
  outputDir: 'reports/artifacts',
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    // Evidence for every test, pass or fail: video, screenshot and a
    // step-by-step trace, all linked from the HTML report.
    video: 'on',
    screenshot: 'on',
    trace: 'on',
    viewport: { width: 1366, height: 820 },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1366, height: 820 },
        permissions: ['microphone'],
        launchOptions: {
          // A fake microphone (a steady tone) so the Live tab can be tested
          // without a person speaking.
          args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
        },
      },
    },
  ],
  webServer: [
    {
      command: `${python} run_backend.py`,
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      env: { E2E_BACKEND_PORT: String(BACKEND_PORT), E2E_FRONTEND_ORIGIN: `http://localhost:${FRONTEND_PORT}` },
    },
    {
      command: `npm --prefix ../frontend run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        VITE_API_URL: `http://127.0.0.1:${BACKEND_PORT}`,
        // Empty Supabase settings put the frontend in dev-login mode:
        // any email signs in as its own local test user.
        VITE_SUPABASE_URL: '',
        VITE_SUPABASE_ANON_KEY: '',
      },
    },
  ],
});
