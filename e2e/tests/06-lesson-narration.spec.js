// Journey 11: Redwan reads a lesson aloud. The word he is saying is
// highlighted and the page follows; the student can pause, ask him out loud
// about that passage, and continue from the same sentence.
import { expect, test, API, LESSON_1, signUp } from './helpers';

/** The narration panel beside the lesson (the phone bar is hidden at this width). */
const narrator = (page) => page.getByRole('status').filter({ hasText: /Listen with Redwan|Reading|Paused|Getting ready|Loading|Finished|Stopped/ });

/** The text of the word highlighted right now (CSS Custom Highlight API). */
const highlightedWord = (page) => page.evaluate(() => {
  const h = CSS.highlights.get('narration-word');
  return h ? [...h][0]?.toString() ?? null : null;
});

test('the lesson is read aloud with the spoken word highlighted; pause, ask, continue', async ({ page }) => {
  const speech = [];
  page.on('request', (req) => {
    if (req.url().startsWith(`${API}/avatar/speech`)) speech.push(req.postDataJSON());
  });
  const liveStarts = [];
  page.on('websocket', (ws) => {
    if (!ws.url().includes('/api/live/ws')) return;
    ws.on('framesent', (frame) => {
      if (typeof frame.payload === 'string' && frame.payload.includes('"start"')) liveStarts.push(JSON.parse(frame.payload));
    });
  });

  await signUp(page);
  await page.goto(`/lessons/${LESSON_1}`);

  // Nothing plays until asked.
  await page.waitForTimeout(1000);
  expect(speech).toEqual([]);

  await page.getByRole('button', { name: 'Start listening' }).click();

  // Reading: one block marked, and the highlighted word moves on.
  await expect(narrator(page).getByText('Reading', { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[data-narrating]')).toHaveCount(1);
  await expect.poll(() => highlightedWord(page)).not.toBeNull();
  const first = await highlightedWord(page);
  await expect.poll(() => highlightedWord(page), { timeout: 10_000 }).not.toBe(first);

  // Lesson audio is asked for as lesson narration, which the backend caches on disk.
  expect(speech[0].purpose).toBe('lesson');
  expect(speech[0].text).not.toMatch(/[#*`]/); // read from the page, not the Markdown

  // Pause stops it where it is.
  await page.getByRole('button', { name: 'Pause' }).click();
  await expect(narrator(page).getByText('Paused', { exact: true })).toBeVisible();
  const pausedOn = await highlightedWord(page);
  await page.waitForTimeout(800);
  expect(await highlightedWord(page)).toBe(pausedOn);

  // Ask: a live call that knows the passage we stopped on.
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page.getByText('Hello Redwan, can you hear me?')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Yes, I can hear you clearly/)).toBeVisible();
  expect(liveStarts).toHaveLength(1);
  expect(liveStarts[0].reading).toBeTruthy();
  expect(liveStarts[0].reading).toContain(pausedOn);
  expect(liveStarts[0].conversation).toBeTruthy(); // saved with the lesson

  // Continue: the call ends and reading carries on, with no part downloaded twice.
  await page.getByRole('button', { name: 'Continue the lesson' }).click();
  await expect(narrator(page).getByText('Reading', { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect.poll(() => highlightedWord(page), { timeout: 10_000 }).not.toBe(pausedOn);
  const texts = speech.map((s) => s.text);
  expect(new Set(texts).size).toBe(texts.length);

  // Close clears every highlight.
  await page.getByRole('button', { name: 'Close narration' }).click();
  await expect(page.locator('[data-narrating]')).toHaveCount(0);
  expect(await highlightedWord(page)).toBeNull();
});

test('clicking a paragraph while listening reads from there', async ({ page }) => {
  await signUp(page);
  await page.goto(`/lessons/${LESSON_1}`);
  await page.getByRole('button', { name: 'Start listening' }).click();
  await expect(narrator(page).getByText('Reading', { exact: true })).toBeVisible({ timeout: 15_000 });

  const target = page.locator('.prose p').nth(3);
  await target.click();
  await expect(target).toHaveAttribute('data-narrating', /block|fallback/);
  const firstWord = (await target.innerText()).trim().split(/\s+/)[0];
  await expect.poll(() => highlightedWord(page), { timeout: 10_000 }).toBe(firstWord);
});

test('half the screen is Redwan; the lesson scrolls in the other half, the page does not', async ({ page }) => {
  await signUp(page);
  await page.goto(`/lessons/${LESSON_1}`);
  const tutor = page.getByRole('region', { name: 'Redwan, your tutor' });
  const lesson = page.getByRole('region', { name: 'Lesson' });
  await expect(tutor).toBeVisible();
  await expect(lesson).toBeVisible();

  // Side by side, roughly half each.
  const [a, b] = [await tutor.boundingBox(), await lesson.boundingBox()];
  expect(Math.abs(a.width - b.width)).toBeLessThan(40);
  expect(b.x).toBeGreaterThan(a.x + a.width - 1);

  // Before starting, the controls are explained in plain words, and there
  // is one thing to press: video connects with Play, not with its own button.
  await expect(page.getByText('Did not get something? Press Ask', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Connect video' })).toHaveCount(0);

  // Scrolling the lesson moves the lesson only; Redwan stays where he was.
  const pane = lesson.locator('.overflow-y-auto').first();
  await pane.evaluate((el) => el.scrollTo(0, 800));
  await expect.poll(() => pane.evaluate((el) => el.scrollTop)).toBeGreaterThan(400);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(5);
  expect((await tutor.boundingBox()).y).toBeCloseTo(a.y, 0);
  await expect(page.getByText(/\d+% read/)).not.toHaveText('0% read');
});
