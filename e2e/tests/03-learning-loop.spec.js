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
  await expect(page.getByText('What he believes')).toBeVisible();
  await expect(page.getByText(/I'm confident my answer was right/)).toBeVisible();

  // The question he must re-take is the one that produced his belief.
  const belief = await page.getByText('What he believes').locator('..').innerText();
  const question = await page.getByText('The question he will re-take').locator('..').innerText();
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
  await expect(page.getByText('You taught him - misconception fixed')).toBeVisible();
});

test('running out of attempts is reported as a fail, never as fixed', async ({ page }) => {
  // Regression: the page used to show "Misconception Addressed" after the
  // third failed retake, directly under "Redwan still got it wrong".
  await signUp(page);
  await failQuiz1(page);
  await page.goto('/tutor?mode=teachback');
  await page.getByRole('button', { name: 'Teach', exact: true }).first().click();
  const box = page.getByPlaceholder('Explain why what he believes is wrong...');
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    await box.fill(`Attempt ${attempt}: no, that is not right at all, think again about it please.`);
    await box.press('Enter');
    await expect(page.getByText(`Attempt ${attempt}:`, { exact: false })).toBeVisible();
    await page.getByRole('button', { name: 'Ask Redwan to re-take the question' }).click();
    await expect(page.getByText('Redwan still got it wrong')).toBeVisible();
    await expect(page.getByText(attempt < 3 ? `${3 - attempt} of 3 left` : 'None left')).toBeVisible();
  }
  await expect(page.getByText('Out of attempts - the belief is still there')).toBeVisible();
  await expect(page.getByText(/misconception fixed|Misconception Addressed/i)).toHaveCount(0);
  await expect(page.getByText('None left')).toBeVisible();

  // Try again opens a fresh session on the same belief.
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByText('3 of 3 left')).toBeVisible();
});

test('pressing Teach again resumes the session instead of starting over', async ({ page }) => {
  await signUp(page);
  await failQuiz1(page);
  await page.goto('/tutor?mode=teachback');
  await page.getByRole('button', { name: 'Teach', exact: true }).first().click();
  const box = page.getByPlaceholder('Explain why what he believes is wrong...');
  await box.fill('Here is my first explanation, which should still be here afterwards.');
  await box.press('Enter');
  await expect(page.getByText(/still don't follow|walk me through/)).toBeVisible();

  await page.getByRole('button', { name: 'All beliefs' }).click();
  await page.getByRole('button', { name: 'Teach', exact: true }).first().click();
  await expect(page.getByText('Here is my first explanation, which should still be here afterwards.')).toBeVisible();
});
