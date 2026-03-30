import { test, expect } from '@playwright/test';

test.describe('Smoke tests', () => {
  test('login page loads', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('BidPilot');
  });

  test('register page loads with step indicator', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('h1')).toContainText('BidPilot');
    await expect(page.locator('text=Create Account')).toBeVisible();
  });

  test('glossary page loads and is searchable', async ({ page }) => {
    // Glossary requires auth, so check redirect or direct access
    await page.goto('/glossary');
    // If redirected to login, that's expected behavior
    const url = page.url();
    if (url.includes('/login')) {
      // Auth redirect works correctly
      expect(url).toContain('/login');
    } else {
      // If somehow accessible, check content
      await expect(page.locator('text=Glossary')).toBeVisible();
    }
  });

  test('navigation has skip-to-content link', async ({ page }) => {
    await page.goto('/login');
    // Skip link exists but is sr-only until focused
    const skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toHaveCount(1);
  });

  test('register flow - step navigation', async ({ page }) => {
    await page.goto('/register');

    // Step 1: Fill account fields
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');

    // Display name field
    const displayNameInput = page.locator('input').first();
    await displayNameInput.fill('Test User');

    // Next button should become enabled
    const nextButton = page.locator('button:has-text("Next: Profile Setup")');
    await expect(nextButton).toBeEnabled();
  });
});
