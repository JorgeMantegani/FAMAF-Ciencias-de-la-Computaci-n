import { expect, test } from './fixtures.js'

async function seed(page, expires_at) {
  await page.goto('/login')
  await page.evaluate(expiry => localStorage.setItem('futbot.session', JSON.stringify({
    access_token: 'access', refresh_token: 'refresh', club_id: 'club', expires_at: expiry,
  })), expires_at)
}

test('recargar no reinicia los cinco minutos', async ({ page }) => {
  const now = new Date()
  await page.clock.install({ time: now })
  await page.route('**/api/auth/me', route => route.fulfill({ json: { user_id: 'user', club_id: 'club' } }))
  await seed(page, Math.floor(now.getTime() / 1000) + 300)
  await page.goto('/home')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  await page.clock.fastForward(180000)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  await page.clock.fastForward(120000)
  await expect(page).toHaveURL('/login')
})

test('una sesión ya vencida no entra a home al volver a abrir la página', async ({ page }) => {
  await seed(page, Math.floor(Date.now() / 1000) - 1)
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => localStorage.getItem('futbot.session'))).toBeNull()
})

test('401 obliga a iniciar sesión sin intentar refresh', async ({ page }) => {
  let refreshes = 0
  await page.route('**/api/auth/me', route => route.fulfill({ status: 401, json: { detail: 'Vencida' } }))
  await page.route('**/api/auth/refresh', route => { refreshes++; return route.abort() })
  await seed(page, Math.floor(Date.now() / 1000) + 300)
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
  expect(refreshes).toBe(0)
  expect(await page.evaluate(() => localStorage.getItem('futbot.session'))).toBeNull()
})
