import { expect, test, type Page } from '@playwright/test';

async function stubMemberMarketplace(page: Page) {
  let selected = false;
  await page.route('**/auth/v1/**', route => route.fulfill({ json: {
    access_token: 'member-token', refresh_token: 'member-refresh', expires_in: 3600,
    token_type: 'bearer', user: { id: 'member-1', email: 'member@example', app_metadata: {} },
  } }));
  await page.route('**/api/config', route => route.fulfill({ json: { auth_configured: true, supabase_url: 'http://127.0.0.1:54321', supabase_anon_key: 'local-demo-key', ai_available: false, voice_available: false, payment_provider: 'simulator' } }));
  await page.route('**/api/me/access', route => route.fulfill({ json: { role: 'member' } }));
  await page.route('**/api/marketplace/cases/case-1/quotations', route => route.fulfill({ json: {
    case_id: 'case-1', status: 'quotes_collected', collection_ready: true, responded: 2, invited: 2, collection_window_hours: 72,
    quotations: [
      { rank: 1, quotation_id: 'quote-real-1', application_id: 'app-1', provider_name: 'Al Noor Takaful', premium_aed: 8200, score: 98, status: selected ? 'selected' : 'submitted', explanation: 'Strong price and network fit from the submitted terms.', terms: { name: 'Al Noor Standard', network: 'standard', annual_limit: 500000, deductible: 500, outpatient_copay_pct: 20, maternity: { covered: true, waiting_period_months: 6 } } },
      ...(!selected ? [{ rank: 2, quotation_id: 'quote-real-2', application_id: 'app-2', provider_name: 'Gulf Shield Insurance', premium_aed: 10500, score: 91, status: 'submitted', explanation: 'Wide access with a higher submitted premium.', terms: { name: 'Gulf Wide', network: 'wide', annual_limit: 800000, deductible: 250, outpatient_copay_pct: 15 } }] : []),
    ],
  } }));
  await page.route('**/api/marketplace/quotations/quote-real-1/select', route => { selected = true; return route.fulfill({ json: { quotation_id: 'quote-real-1', application_id: 'app-1', status: 'selected' } }); });
}

test('member compares and selects ranked real provider quotations', async ({ page }) => {
  await stubMemberMarketplace(page);
  await page.goto('/login');
  await page.getByLabel('Email address').fill('member@example');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.goto('/app/marketplace/case-1');
  await expect(page.getByRole('heading', { name: 'Your provider quotations' })).toBeVisible();
  await expect(page.getByText('AED 8,200.00')).toBeVisible();
  await page.getByRole('button', { name: /Select this quotation/ }).first().click();
  await expect(page.getByText(/chosen provider has been notified/i)).toBeVisible();
  await page.screenshot({ path: 'PIVOT_V2_PHASE6_MEMBER_SELECTION.png', fullPage: true });
});
