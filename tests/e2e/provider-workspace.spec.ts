import { expect, test, type Page } from '@playwright/test';

const config = {
  auth_configured: true,
  supabase_url: 'http://127.0.0.1:54321',
  supabase_anon_key: 'local-demo-key',
  ai_available: false,
  voice_available: false,
  payment_provider: 'simulator',
};

async function stubProviderApi(page: Page) {
  await page.route('**/auth/v1/**', route => route.fulfill({ json: {
    access_token: 'provider-token', refresh_token: 'provider-refresh', expires_in: 3600,
    token_type: 'bearer', user: { id: 'provider-user-1', email: 'provider@example', app_metadata: { helm_role: 'provider' } },
  } }));
  await page.route('**/api/config', route => route.fulfill({ json: config }));
  await page.route('**/api/me/access', route => route.fulfill({ json: { role: 'provider' } }));
  await page.route('**/api/provider/applications', route => route.fulfill({ json: [{
    id: 'application-12345678', status: 'sent_to_providers', created_at: '2026-09-19T08:30:00Z',
    consent_snapshot: { emirate: 'Dubai', age: 34, cover_for: 'self', budget_aed: 12000, hospital_preference: 'Wide network' },
  }] }));
  await page.route('**/api/provider/quotations', route => route.fulfill({ json: [
    { id: 'quote-selected', application_id: 'application-selected', premium: 9200, status: 'selected', plan_terms: { network: 'standard' }, submitted_at: '2026-09-19T09:00:00Z' },
    { id: 'quote-accepted', application_id: 'application-accepted', premium: 10400, status: 'accepted', plan_terms: { network: 'wide' }, submitted_at: '2026-09-19T09:15:00Z' },
  ] }));
  await page.route('**/api/provider/policies', route => route.fulfill({ json: [{ id: 'policy-12345678', application_id: 'application-bound', quotation_id: 'quote-bound', status: 'active', started_at: '2026-09-19T10:00:00Z' }] }));
  await page.route('**/api/provider/policies/policy-12345678/payments', route => route.fulfill({ json: [{ id: 'payment-1', amount: 10400, status: 'paid', paid_at: '2026-09-19T10:05:00Z' }] }));
  await page.route('**/api/provider/applications/application-12345678/assistant', route => route.fulfill({ json: { draft: 'Consented application includes age, budget, cover and hospital preference.' } }));
}

test('provider sees the isolated applications, quotation, policy and account workspace', async ({ page }) => {
  await stubProviderApi(page);
  await page.goto('/login');
  await page.getByLabel('Email address').fill('provider@example');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/provider$/);
  await page.getByRole('button', { name: /Application applicat/ }).click();
  await expect(page.getByText('hospital preference')).toBeVisible();
  await page.getByRole('button', { name: 'Summarize' }).click();
  await expect(page.getByText(/Consented application includes/)).toBeVisible();
  await page.getByRole('button', { name: /Policy policy-1/ }).click();
  await expect(page.getByRole('cell', { name: /AED.*10,400/ })).toBeVisible();
  await page.screenshot({ path: 'PIVOT_V2_PHASE5_PROVIDER_DESKTOP.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'PIVOT_V2_PHASE5_PROVIDER_MOBILE.png', fullPage: true });
});
