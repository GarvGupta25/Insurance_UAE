import { expect, test, type Page } from '@playwright/test';

const config = {
  auth_configured: false,
  supabase_url: '',
  supabase_anon_key: '',
  ai_available: false,
  voice_available: false,
  payment_provider: 'simulator',
};

const catalogue = {
  plans: [
    { id: 'plan_a', name: 'Harbour Basic', network: 'community', annual_premium: 4200, network_note: 'Community clinics' },
    { id: 'plan_b', name: 'Crescent Choice', network: 'standard', annual_premium: 8900, network_note: 'Standard hospitals' },
    { id: 'plan_c', name: 'Palm Plus', network: 'premium', annual_premium: 16500, network_note: 'Premium hospitals' },
  ],
};

async function stubPublicApi(page: Page) {
  await page.route('**/api/config', route => route.fulfill({ json: config }));
  await page.route('**/api/catalogue', route => route.fulfill({ json: catalogue }));
}

test('public journey is keyboard-accessible and labels the demonstration', async ({ page }) => {
  await stubPublicApi(page);
  await page.goto('/');

  // Check new hero heading
  await expect(page.getByRole('heading', { name: 'Individual health cover for UAE residents.' })).toBeVisible();
  
  // Check new demo product disclaimer
  await expect(page.getByText('Demo product - plans and pricing shown are fictional, for illustration only.')).toBeVisible();
  
  // Check that fetched plans are rendering
  await expect(page.getByRole('heading', { name: 'Harbour Basic' })).toBeVisible();

  // Test the primary CTA link (Find my cover)
  await page.getByRole('link', { name: 'Find my cover' }).first().focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Account access is not configured yet.')).toBeVisible();
});

test('public landing stays usable at a mobile width', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await stubPublicApi(page);
  await page.goto('/');

  // Check hero heading
  await expect(page.getByRole('heading', { name: 'Individual health cover for UAE residents.' })).toBeVisible();
  
  // Desktop nav should be hidden on mobile
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).not.toBeVisible();

  // Click the hamburger menu to open mobile panel
  await page.getByRole('button', { name: 'Open navigation' }).click();

  // Now "Sign in" should be visible
  await expect(page.getByRole('link', { name: 'Sign in' }).first()).toBeVisible();

  await context.close();
});
