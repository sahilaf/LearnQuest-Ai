// Journeys 5, 6 and 10: the tutor page - chat, the live voice call, and the
// avatar, which must never connect or play on its own.
import { expect, test, API, signUp } from './helpers';

test('opening the tutor page connects nothing and plays nothing', async ({ page }) => {
  await signUp(page);
  const avatarCalls = [];
  page.on('request', (req) => {
    const url = req.url();
    if (url.startsWith(`${API}/avatar/session`) || url.startsWith(`${API}/avatar/speech`)) avatarCalls.push(url);
  });
  // Our sockets only - the dev server keeps its own live-reload socket open.
  page.on('websocket', (ws) => {
    if (/:8100|:5001/.test(ws.url())) avatarCalls.push(ws.url());
  });
  await page.goto('/tutor');
  await expect(page.getByRole('button', { name: 'Connect video' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start conversation' })).toBeVisible();
  await page.waitForTimeout(2000);
  expect(avatarCalls).toEqual([]);
});

test('with no GPU service, Connect says the avatar is offline and offers a way back', async ({ page }) => {
  await signUp(page);
  await page.goto('/tutor');
  await page.getByRole('button', { name: 'Connect video' }).click();
  await expect(page.getByText('Avatar offline')).toBeVisible();
  await expect(page.getByText('The avatar service is not configured on this machine.')).toBeVisible();
  await page.getByRole('button', { name: 'Back' }).click();
  await expect(page.getByRole('button', { name: 'Connect video' })).toBeVisible();
});

test('chat: a question gets an answer, and the conversation survives a reload', async ({ page }) => {
  await signUp(page);
  await page.goto('/tutor?tab=chat');
  const input = page.getByPlaceholder(/Ask your tutor a question/);
  await input.fill('What is a foreign key?');
  await input.press('Enter');
  await expect(page.getByText('[e2e tutor] You asked: "What is a foreign key?"')).toBeVisible();

  await page.reload();
  await page.getByRole('tab', { name: /Chat/ }).click();
  await page.getByText('What is a foreign key?').first().waitFor();
  await expect(page.getByText('[e2e tutor] You asked: "What is a foreign key?"')).toBeVisible();
});

test('live call: speak, see both sides of the conversation, then find it in Chat', async ({ page }) => {
  await signUp(page);
  await page.goto('/tutor');
  await page.getByRole('button', { name: 'Start conversation' }).click();

  // The browser's fake microphone (a steady tone) stands in for a voice; the
  // scripted live tutor answers after a second of it.
  await expect(page.getByText('Hello Redwan, can you hear me?')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Yes, I can hear you clearly/)).toBeVisible();
  await expect(page.getByText('Redwan', { exact: true }).first()).toBeVisible();

  // Typing mid-call works too.
  await page.getByPlaceholder(/Prefer typing/).fill('What is normalization?');
  await page.getByPlaceholder(/Prefer typing/).press('Enter');
  await expect(page.getByText('[e2e tutor] You said: What is normalization?')).toBeVisible();

  await page.getByRole('button', { name: 'End call' }).click();
  await expect(page.getByRole('button', { name: 'Start conversation' })).toBeVisible();

  // One tutor, not three: the call is in the chat history.
  await page.getByRole('tab', { name: /Chat/ }).click();
  await expect(page.getByText(/Yes, I can hear you clearly/).first()).toBeVisible();
});

test('live call: the status always says whose turn it is', async ({ page }) => {
  await signUp(page);
  await page.goto('/tutor');
  await page.getByRole('button', { name: 'Start conversation' }).click();
  const status = page.getByRole('status').first();
  await expect(status).toContainText(/Your turn|Listening|Thinking|Redwan is speaking/, { timeout: 20_000 });
  await expect(page.getByText('Redwan is speaking').first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: 'End call' }).click();
});
