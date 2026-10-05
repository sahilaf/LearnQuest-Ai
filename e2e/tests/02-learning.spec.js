// Journey 2: find a course, open a lesson, read it.
import { expect, test, LESSON_1, SQL_COURSE, signUp } from './helpers';

test('browse the catalogue, open a course and its first lesson', async ({ page }) => {
  await signUp(page);
  await page.goto('/learn?tab=browse');
  await expect(page.getByRole('link', { name: 'Mastering Relational Databases & SQL' }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Mastering Relational Databases & SQL' }).first().click();
  await expect(page).toHaveURL(new RegExp(`/courses/${SQL_COURSE}`));
  await expect(page.getByText('Track Curriculum')).toBeVisible();

  await page.getByRole('link', { name: /The Relational Model, Entities & Keys/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`/lessons/${LESSON_1}`));
  await expect(page.getByText('Candidate Keys, Primary Keys and Superkeys').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Quiz me/ }).first()).toBeVisible();
});
