import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  use: {
    baseURL: process.env.UI_BASE_URL || 'http://localhost:8090',
    headless: true,
    viewport: { width: 1280, height: 900 },
  },
  webServer: {
    command: 'python -m http.server 8090',
    port: 8090,
    reuseExistingServer: true,
    cwd: '.',
    timeout: 120000
  },
  reporter: [['list']]
});