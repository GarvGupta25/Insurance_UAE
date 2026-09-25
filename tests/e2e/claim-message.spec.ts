import { expect, test } from '@playwright/test';

test('member message is saved when image OCR is unavailable', async ({ page }) => {
  const message = 'I visited Crescent Demo Clinic and received a bill for AED 735.';
  let submitted: any;
  await page.route('**/auth/v1/**', route => route.fulfill({ json: {
    access_token: 'member-token', refresh_token: 'member-refresh', expires_in: 3600,
    token_type: 'bearer', user: { id: 'member-1', email: 'member@example', app_metadata: {} },
  } }));
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/config') return route.fulfill({ json: {
      auth_configured: true, supabase_url: 'http://127.0.0.1:54321', supabase_anon_key: 'local-demo-key',
      ai_available: false, voice_available: false, payment_provider: 'simulator',
    } });
    if (url.pathname === '/api/me/access') return route.fulfill({ json: { role: 'member' } });
    if (url.pathname === '/api/policies/policy-demo') return route.fulfill({ json: {
      status: 'demo_active', plan: { id: 'plan_b', name: 'Balanced', annual_premium: 9000,
        annual_limit: 500000, deductible: 500, outpatient_copay_pct: 20, network: 'standard',
        maternity: { covered: false }, chronic_preexisting: { covered: false } },
      servicing: [], instalments: [],
    } });
    if (url.pathname.endsWith('/attachments/parse')) return route.fulfill({ status: 503, json: { message: 'Local image OCR is unavailable.' } });
    if (url.pathname.endsWith('/claim-intakes/free-form')) {
      submitted = route.request().postDataJSON();
      return route.fulfill({ json: { intake_id: 'claim-demo', kind: 'pending', route: 'review', follow_up: 'Which provider?' } });
    }
    if (url.pathname === '/api/policies/policy-demo/claim-intakes') return route.fulfill({ json: [] });
    if (url.pathname === '/api/cases' || url.pathname === '/api/policies' || url.pathname === '/api/marketplace/notifications') return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });

  await page.goto('/login');
  await page.getByLabel('Email address').fill('member@example');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.goto('/app/policies/policy-demo');
  await page.getByRole('button', { name: 'Claim Center' }).click();
  await page.getByLabel('Your message').fill(message);
  await page.locator('.claim-attachment input[type=file]').setInputFiles({
    name: 'sample-invoice.png', mimeType: 'image/png', buffer: Buffer.from('89504e470d0a1a0a', 'hex'),
  });
  await page.getByRole('button', { name: 'Submit claim message' }).click();

  await expect(page.getByText('✨ We received your message.')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('sample-invoice.png could not be read');
  expect(submitted).toEqual({ message, documents: [] });
});
