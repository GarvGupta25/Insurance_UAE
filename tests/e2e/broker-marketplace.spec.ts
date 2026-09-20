import { expect, test, type Page } from '@playwright/test';

const config = {
  auth_configured: true,
  supabase_url: 'http://127.0.0.1:54321',
  supabase_anon_key: 'local-demo-key',
  ai_available: false,
  voice_available: false,
  payment_provider: 'simulator',
};

async function stubBrokerApi(page: Page) {
  await page.route('**/auth/v1/**', route => route.fulfill({
    json: {
      access_token: 'broker-token',
      refresh_token: 'broker-refresh',
      expires_in: 3600,
      token_type: 'bearer',
      user: { id: 'broker-1', email: 'broker@example', app_metadata: { helm_role: 'broker' } },
    },
  }));
  await page.route('**/api/config', route => route.fulfill({ json: config }));
  await page.route('**/api/me/access', route => route.fulfill({ json: { role: 'broker' } }));
  await page.route('**/api/broker/recommendations', route => route.fulfill({ json: [] }));
  await page.route('**/api/broker/appeals', route => route.fulfill({ json: [] }));
  await page.route('**/api/broker/reassessments', route => route.fulfill({ json: [] }));
  await page.route('**/api/broker/worklist', route => route.fulfill({ json: [
    { id: 'app-2', item_type: 'marketplace_checkpoint_2', applicant_id: 'member-1', case_id: 'case-1', age_days: 3, priority_rank: 1, priority_reason: '3 day(s) unresolved; Checkpoint 2 blocks policy binding.' },
    { id: 'app-1', item_type: 'marketplace_checkpoint_1', applicant_id: 'member-1', case_id: 'case-1', age_days: 1, priority_rank: 2, priority_reason: '1 day unresolved; Checkpoint 1 blocks provider submission.' },
  ] }));
  await page.route('**/api/broker/marketplace/applications', route => route.fulfill({ json: [
    { id: 'app-1', case_id: 'case-1', applicant_id: 'member-1', provider_id: 'provider-1', status: 'broker_final_review' },
  ] }));
  await page.route('**/api/broker/marketplace/provider-performance', route => route.fulfill({ json: [
    { provider_id: 'pearl', provider_name: 'Pearl Health Partners', average_turnaround_hours: 2, submitted: 4, selected: 2, win_rate_pct: 50 },
    { provider_id: 'al-noor', provider_name: 'Al Noor Takaful', average_turnaround_hours: 12, submitted: 4, selected: 1, win_rate_pct: 25 },
  ] }));
  await page.route('**/api/broker/marketplace/applications/app-1', route => route.fulfill({ json: {
    id: 'app-1',
    case_id: 'case-1',
    applicant_id: 'member-1',
    status: 'broker_final_review',
    quotations: [
      { id: 'quote-1', provider: 'Al Noor Takaful', premium: 8900, key_terms: { network: 'standard', deductible: 500, outpatient_copay_pct: 20 }, status: 'accepted', submitted_at: '2026-09-18T08:30:00Z' },
      { id: 'quote-2', provider: 'Gulf Shield Insurance', premium: 12400, key_terms: { network: 'wide', deductible: 250, outpatient_copay_pct: 10 }, status: 'submitted', submitted_at: '2026-09-18T09:15:00Z' },
      { id: 'quote-3', provider: 'Pearl Health Partners', premium: 10250, key_terms: { network: 'standard', deductible: 300, outpatient_copay_pct: 15 }, status: 'submitted', submitted_at: '2026-09-18T09:45:00Z' },
    ],
    checkpoint_history: [
      { checkpoint: 'checkpoint_1', approved_by: 'broker-1', approved_at: '2026-09-17T10:00:00Z', action: 'edit', note: 'Adjusted the supported plan.', edits: { plan_id: 'plan-b' } },
      { checkpoint: 'checkpoint_2', approved_by: 'broker-1', approved_at: '2026-09-19T10:00:00Z', action: 'approve', note: 'Final provider terms checked.', edits: {} },
    ],
  } }));
  await page.route('**/api/broker/cases/member-1', route => route.fulfill({ json: {
    applicant_id: 'member-1', profile: {}, classification: { cohort: 'standard', flags: [] }, review_history: [], next_action_needed: 'Marketplace checkpoint required', servicing_history: [],
  } }));
}

test('broker compares marketplace quotations and both checkpoints', async ({ page }) => {
  await stubBrokerApi(page);
  await page.goto('/login');
  await page.getByLabel('Email address').fill('broker@example');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.goto('/app/broker');
  await page.getByRole('button', { name: /Case case-1/ }).click();

  await expect(page.getByRole('heading', { name: 'Provider quotations and checkpoints' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pearl Health Partners' })).toBeVisible();
  await expect(page.getByText('2h', { exact: true })).toBeVisible();
  await expect(page.getByText('Al Noor Takaful', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('checkpoint 1', { exact: true })).toBeVisible();
  await expect(page.getByText('checkpoint 2', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'PIVOT_V2_PHASE7_BROKER_PERFORMANCE_DESKTOP.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'PIVOT_V2_PHASE7_BROKER_PERFORMANCE_MOBILE.png', fullPage: true });
});
