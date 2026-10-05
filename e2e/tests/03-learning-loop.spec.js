// Journey 3 - the project's central claim, end to end:
// a wrong answer -> the false belief behind it is named -> Redwan is one
// click away to talk it through.
import { expect, test, dismissCelebrations, failQuiz1, signUp } from './helpers';

test('a wrong quiz answer names the misconception behind it', async ({ page }) => {
  await signUp(page);
  await failQuiz1(page);
  await dismissCelebrations(page);

  await expect(page.getByText('MISCONCEPTION DETECTED', { exact: false })).toBeVisible();
  await expect(page.getByText(/You believe/).first()).toBeVisible();

  // The next step is a conversation with the tutor, in the Chat tab.
  await page.getByRole('link', { name: /Ask Redwan about it/ }).first().click();
  await expect(page).toHaveURL(/\/tutor\?tab=chat/);
  await expect(page.getByRole('tab', { name: /Chat/, selected: true })).toBeVisible();
});

test('the tutor has two modes - Live and Chat', async ({ page }) => {
  await signUp(page);
  await page.goto('/tutor');
  await expect(page.getByRole('tab')).toHaveCount(2);
  await expect(page.getByRole('tab', { name: /Live/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Chat/ })).toBeVisible();

  // An old Teach-Back link still opens the page, on Live.
  await page.goto('/tutor?mode=teachback');
  await expect(page.getByRole('tab', { name: /Live/, selected: true })).toBeVisible();
});
