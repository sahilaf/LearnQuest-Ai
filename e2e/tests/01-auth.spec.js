// Journey 1 and 9: signing up, signing out and back in, and what happens when
// the backend refuses a session.
import { expect, test, API, signUp } from './helpers';

test('a new student signs up and lands on their dashboard', async ({ page }) => {
  await signUp(page, 'Ayesha Rahman');
  await expect(page.getByText('Welcome back,', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Tutor' })).toBeVisible();
});

test('signing out returns to the public site, and signing in again works', async ({ page }) => {
  const { email } = await signUp(page);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).not.toHaveURL(/\/dashboard/);

  await page.goto('/login');
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill('e2e-pass-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
});

test('a protected page sends a signed-out visitor to log in', async ({ page }) => {
  await page.goto('/tutor');
  await expect(page).toHaveURL(/\/login/);
});

test('a session the backend rejects ends on the landing page with a notice', async ({ page }) => {
  await signUp(page);
  // The backend answering 401 is how an expired or forged session looks.
  // (Forged tokens themselves are covered by backend/tests/test_auth_hardening.py.)
  await page.route(`${API}/**`, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"expired"}' }));
  await page.goto('/learn');
  await expect(page).toHaveURL(/localhost:\d+\/$/);
  await expect(page.getByText('Your session ended.')).toBeVisible();
});
