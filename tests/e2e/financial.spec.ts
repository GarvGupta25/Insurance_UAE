import { expect, test } from '@playwright/test';

test('member explores and saves a financial scenario on mobile', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const plans = [
    { id: 'plan_a', name: 'Essential', annual_premium: 4200, annual_limit: 150000, deductible: 1500, outpatient_copay_pct: 30, network: 'restricted', dental_optical: 'none', maternity: { covered: false }, chronic_preexisting: { covered: false } },
    { id: 'plan_b', name: 'Balanced', annual_premium: 8900, annual_limit: 500000, deductible: 500, outpatient_copay_pct: 20, network: 'standard', dental_optical: 'basic', maternity: { covered: true, waiting_period_months: 12, limit: 10000 }, chronic_preexisting: { covered: true, waiting_period_months: 6 } },
    { id: 'plan_c', name: 'Comprehensive', annual_premium: 16500, annual_limit: 1500000, deductible: 0, outpatient_copay_pct: 10, network: 'wide', dental_optical: 'full', maternity: { covered: true, waiting_period_months: 3, limit: 25000 }, chronic_preexisting: { covered: true, waiting_period_months: 0 } },
  ];
  const items = plans.map(plan => ({ plan, status: 'supported', premium_fils: plan.annual_premium * 100,
    monthly_budget_equivalent_fils: Math.round(plan.annual_premium * 100 / 12), reasons: ['Saved profile fit'], gaps: [], unknowns: [], tradeoffs: [] }));
  await page.route('**/api/config', route => route.fulfill({ json: { auth_configured: true,
    supabase_url: 'http://127.0.0.1:54321', supabase_anon_key: 'synthetic-anon-key',
    ai_available: false, voice_available: false, payment_provider: 'simulator' } }));
  await page.route('**/auth/v1/token**', route => route.fulfill({ json: {
    access_token: 'synthetic-token', refresh_token: 'synthetic-refresh', token_type: 'bearer',
    expires_in: 360000, expires_at: Math.floor(Date.now() / 1000) + 360000,
    user: { id: '00000000-0000-4000-8000-000000000001', email: 'member@example.test',
      aud: 'authenticated', role: 'authenticated', app_metadata: {}, user_metadata: {},
      created_at: new Date().toISOString() },
  } }));
  await page.route('**/api/quotes/quote-1', route => route.fulfill({ json: { id: 'quote-1', case_id: 'case-1',
    applicant_name: 'Demo Member', generated_at: new Date().toISOString(), items,
    recommended_plan_id: 'plan_a', stale: false } }));
  await page.route('**/api/me/profile', route => route.fulfill({ json: { version: 2, facts: {
    annual_budget: 12000, contribution_aed: 0, cost_sharing: 'balanced' } } }));
  await page.route('**/api/me/access', route => route.fulfill({ json: { role: 'member' } }));
  await page.route('**/api/policies', route => route.fulfill({ json: [] }));
  await page.route('**/api/cases', route => route.fulfill({ json: [] }));
  await page.route('**/api/cases/case-1', route => route.fulfill({ json: { messages: [], active_runs: [] } }));
  await page.route('**/api/sources', route => route.fulfill({ json: { items: [] } }));
  let savedCount = 0;
  let savedInputs: unknown = {};
  await page.route('**/api/quotes/quote-1/financial-scenarios', route => {
    if (route.request().method() === 'POST') {
      savedCount += 1;
      savedInputs = route.request().postDataJSON();
      return route.fulfill({ json: { id: 'scenario-1', inputs: savedInputs, result: {} } });
    }
    return route.fulfill({ json: { items: savedCount ? [{ id: 'scenario-1', inputs: savedInputs, result: {} }] : [] } });
  });
  await page.route('**/api/quotes/quote-1/financial-preview', async route => {
    const input = route.request().postDataJSON();
    const chosen = input.priority === 'lower_member_cost' ? 'plan_c' : 'plan_a';
    await route.fulfill({ json: { recommended_plan_id: chosen,
      reply: `${chosen === 'plan_c' ? 'Comprehensive' : 'Essential'} is the best supported fictional option.`,
      assumptions: ['Monthly amounts are budgeting equivalents.'],
      rows: plans.map(plan => ({ plan_id: plan.id, name: plan.name, fit_status: 'supported',
        premium_fils: plan.annual_premium * 100, member_premium_fils: plan.annual_premium * 100,
        monthly_budget_equivalent_fils: Math.round(plan.annual_premium * 100 / 12),
        illustrative_member_care_fils: 100000, annual_planning_total_fils: plan.annual_premium * 100 + 100000,
        within_budget: true, budget_gap_fils: 0, gaps: [], unknowns: [] })) } });
  });
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Email address' }).fill('member@example.test');
  await page.getByLabel('Password').fill('synthetic-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.goto('/app/quotes/quote-1');
  await expect(page.getByRole('heading', { name: 'Explore what each plan could mean for your budget.' })).toBeVisible();
  await expect(page.getByText('Tell me your monthly premium budget, an outpatient spending amount to model')).toBeVisible();
  expect(await page.locator('.financial-planner').evaluate(element => element.getBoundingClientRect().right <= innerWidth + 1)).toBe(true);
  await expect(page.getByText('Essential is the best supported fictional option.')).toBeVisible();
  await page.getByRole('button', { name: 'Lower cost when care happens' }).click();
  await expect(page.getByText('Comprehensive is the best supported fictional option.')).toBeVisible();
  await expect(page.getByText('This is your budgeting limit, not an instalment offer.')).toBeVisible();
  await page.getByRole('button', { name: 'Save this scenario' }).click();
  await expect(page.getByText('Saved to this quotation.')).toBeVisible();
  expect(savedCount).toBe(1);
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.getByRole('heading', { name: 'Explore what each plan could mean for your budget.' })).toBeVisible();
  expect(await page.locator('.financial-planner').evaluate(element => element.getBoundingClientRect().right <= innerWidth + 1)).toBe(true);
  await context.close();
});
