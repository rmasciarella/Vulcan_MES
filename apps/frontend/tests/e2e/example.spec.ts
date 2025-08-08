import { test, expect } from '@playwright/test'

test('homepage has app title and nav', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/Vulcan MES|Next\.js|Vulcan/i)
  await expect(page.getByRole('navigation')).toBeVisible()
})
