// Journeys 3 and 4 - the project's central claim, end to end:
// a wrong answer -> the false belief behind it is named -> the student teaches
// Redwan out of it -> Redwan re-takes the question -> his score is the grade.
import { expect, test, QUIZ_1_ANSWERS, dismissCelebrations, failQuiz1, signUp } from './helpers';

test('a wrong quiz answer names the misconception behind it', async ({ page }) => {
  await signUp(page);
  await failQuiz1(page);
  await dismissCelebrations(page);

  await expect(page.getByText('MISCONCEPTION DETECTED', { exact: false })).toBeVisible();
  await expect(page.getByText(/You believe/).first()).toBeVisible();
  await expect(page.getByRole('link', { name: /Teach Redwan to fix it/ }).first()).toBeVisible();
});

test('teaching Redwan: vague is refused, a real explanation passes the retake', async ({ page }) => {
  await signUp(page);
  await failQuiz1(page);
  await dismissCelebrations(page);

  await page.goto('/tutor?mode=teachback');
  await dismissCelebrations(page);
  await page.getByRole('button', { name: 'Teach', exact: true }).first().click();

  // Redwan holds the belief and opens the conversation.
  await expect(page.getByText('He believes:')).toBeVisible();
  await expect(page.getByText(/I'm confident my answer was right/)).toBeVisible();

  // The question he must re-take is the one that produced his belief.
  const belief = await page.getByText('He believes:').locator('..').innerText();
  const question = await page.getByText('His question:').locator('..').innerText();
  const wrongAnswer = /"([^"]+)"/.exec(belief)[1];
  expect(wrongAnswer).toBe('SET NULL');
  expect(question).toContain('ON DELETE');
  const correct = Object.entries(QUIZ_1_ANSWERS).find(([q]) => question.includes(q))[1];

  // A non-explanation is pushed back on.
  const box = page.getByPlaceholder('Explain why what he believes is wrong...');
  await box.fill('You are wrong.');
  await box.press('Enter');
  await expect(page.getByText(/walk me through why|still don't follow/)).toBeVisible();

  // A real explanation convinces him.
  await box.fill(
    'SET NULL keeps the child rows and only blanks their reference, because it is meant for '
    + 'optional links. Removing the child rows together with the parent needs cascading '
    + `deletes, so the answer is ${correct}.`,
  );
  await box.press('Enter');
  await expect(page.getByText('that explains where my reasoning went wrong')).toBeVisible();

  // The retake is the measurement.
  await page.getByRole('button', { name: 'Ask Redwan to re-take the question' }).click();
  await expect(page.getByText(new RegExp(`He answered:.*${correct}`))).toBeVisible();
  await expect(page.getByText(/still got it wrong/)).toHaveCount(0);
});
