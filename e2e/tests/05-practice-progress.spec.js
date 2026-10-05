// Journeys 7 and 8: SQL practice graded by really running the query, and the
// gamification that rewards it.
import { expect, test, PRACTICE_DUPLICATE_EMAILS, dismissCelebrations, failQuiz1, signUp } from './helpers';

test('a correct SQL answer passes the hidden test cases; a wrong one does not', async ({ page }) => {
  await signUp(page);
  await page.goto('/learn?tab=sql-challenges');
  await page.getByRole('link', { name: PRACTICE_DUPLICATE_EMAILS }).click();
  const editor = page.getByPlaceholder('Write your code or query here...');

  await editor.fill('SELECT email FROM users');
  await page.getByRole('button', { name: /Submit Code/ }).click();
  await expect(page.getByText(/fail|wrong|incorrect|mismatch/i).first()).toBeVisible();

  await editor.fill(
    'SELECT email, COUNT(*) AS uses FROM users GROUP BY email HAVING COUNT(*) > 1 ORDER BY email',
  );
  await page.getByRole('button', { name: /Submit Code/ }).click();
  await expect(page.getByText(/accepted|all tests passed|passed/i).first()).toBeVisible();
});

test('finishing a quiz earns XP and a badge, and the student appears on the leaderboard', async ({ page }) => {
  const { name } = await signUp(page, 'Leaderboard Lena');
  await failQuiz1(page);
  await dismissCelebrations(page);

  await page.goto('/progress?tab=achievements');
  await dismissCelebrations(page);
  // At least one: time-of-day badges (Night Owl, Early Bird) can add more.
  await expect(page.getByText(/Badges Earned\s*[1-9]\d*\s*\/\s*15/)).toBeVisible();

  await page.goto('/progress?tab=leaderboard');
  await expect(page.getByText(name).first()).toBeVisible();
  await expect(page.getByText('You').first()).toBeVisible();
});
