import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

const bundledChrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const executablePath = process.platform === 'win32' && existsSync(bundledChrome) ? bundledChrome : undefined;

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    launchOptions: executablePath ? { executablePath } : undefined,
  },
  webServer: {
    command: 'npm --prefix frontend run dev -- --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
});
