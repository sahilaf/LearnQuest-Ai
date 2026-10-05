// Shared steps for the end-to-end suite.
import { expect, test as base } from '@playwright/test';

/**
 * `test` with one addition: badge celebrations ("Awesome!") pop up whenever
 * the backend awards one, at moments no test can predict, and cover the page.
 * Playwright dismisses one automatically whenever it blocks the next action.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addLocatorHandler(page.getByRole('button', { name: 'Awesome!' }), async (button) => {
      await button.click();
    });
    await use(page);
  },
});
export { expect };

/** The test backend (see playwright.config.js). Match API calls against this,
 *  never a bare "/api/" - the frontend's own source files live under src/api/. */
export const API = 'http://127.0.0.1:8100/api';

// Seeded content (backend/app/seed) - fixed ids, so tests can go straight there.
export const SQL_COURSE = 'mastering-relational-databases-sql';
export const LESSON_1 = '22222222-2222-2222-2222-222222220001';
export const QUIZ_1 = '33333333-3333-3333-3333-333333330001';
// Practice problems get fresh ids on every seed, so tests open them by title.
export const PRACTICE_DUPLICATE_EMAILS = 'Emails used more than once';

// Quiz 1 - question text -> correct answer, so a test can answer wrong on
// purpose and know what Redwan must be taught.
export const QUIZ_1_ANSWERS = {
  'What is a Candidate Key': 'A minimal superkey with no unnecessary attributes',
  'MUST have the exact same column name': 'False',
  'ON DELETE ______': 'CASCADE',
  'always point to valid, existing primary keys': 'Referential Integrity',
};

let counter = 0;

/** A brand-new student, signed up through the real form. */
export async function signUp(page, name = 'Test Student') {
  counter += 1;
  const email = `student.${Date.now()}.${counter}@learnquest.test`;
  await page.goto('/register');
  await page.getByPlaceholder('Sarah Chen').fill(name);
  await page.getByPlaceholder('sarah@example.com').fill(email);
  await page.getByPlaceholder('At least 6 characters').fill('e2e-pass-123');
  await page.getByPlaceholder('Repeat your password').fill('e2e-pass-123');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  return { email, name };
}

/** Badge celebrations pop up after milestones; close any that appear. */
export async function dismissCelebrations(page) {
  const ok = page.getByRole('button', { name: 'Awesome!' });
  while (await ok.isVisible().catch(() => false)) {
    await ok.click();
    await page.waitForTimeout(300);
  }
}

/** Take quiz 1 answering every question wrong. Lands on the result page. */
export async function failQuiz1(page) {
  await page.goto(`/quiz/${QUIZ_1}`);
  await page.getByText('Any combination of attributes that uniquely identifies a row').click();
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByRole('button', { name: 'True', exact: true }).click();
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByPlaceholder('Type your exact answer here...').fill('SET NULL');
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByPlaceholder('Explain the concept concisely in your own words...').fill('Uniqueness of rows');
  await page.getByRole('button', { name: /Submit Quiz Attempt/ }).first().click();
  await page.getByRole('button', { name: 'Confirm Submission' }).click();
  await expect(page).toHaveURL(/\/quiz\/attempts\//, { timeout: 30_000 });
  // The misconception is captured in the background after submitting; the
  // result page shows it once it exists. Later steps depend on it.
  await expect(page.getByText('MISCONCEPTION DETECTED', { exact: false })).toBeVisible({ timeout: 30_000 });
}
