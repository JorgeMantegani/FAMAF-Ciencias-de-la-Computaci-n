import { expect, test } from './fixtures.js'

const session = {
  expires_at: Math.floor(Date.now() / 1000) + 300,
  access_token: 'token-simulado',
  refresh_token: 'refresh-simulado',
  club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd',
}

const LEAGUE_ID = '44444444-4444-4444-8444-444444444444'
const CODE = 'a1b2c3d4'

const players = ['Ana', 'Beto', 'Carla', 'Dani', 'Eva', 'Fito'].map((name) => ({
  id: `player-${name.toLowerCase()}`,
  name,
}))

const behaviors = [{ id: 'behavior-front', name: 'Delantero' }]

const private_league = {
  leagueId: LEAGUE_ID,
  name: 'Liga Privada',
  isPrivate: true,
  status: 'waitingGuest',
  minClubs: 3,
  maxClubs: 4,
  enrolledClubs: 1,
  matchDurationMinutes: 10,
  isEnrolled: false,
  mySquad: null,
}

const not_found = {
  status: 404,
  json: { detail: 'La liga no existe', error_code: 'LEAGUE_NOT_FOUND' },
}

const selection_of = (slice) =>
  slice.map((player) => ({ playerId: player.id, behaviorId: behaviors[0].id }))

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } })
  )
  await page.route('**/api/players', (route) => route.fulfill({ json: players }))
  await page.route('**/api/behaviors', (route) => route.fulfill({ json: behaviors }))
  await page.routeWebSocket(/\/ws\/leagues$/, (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type !== 'auth') return
      ws.send(JSON.stringify({ type: 'leagues', name: '', leagues: [] }))
    })
  })
})

async function open_modal(page) {
  await page.goto('/login')
  await page.evaluate(
    (value) => localStorage.setItem('futbot.session', JSON.stringify(value)),
    session
  )
  await page.goto('/home')
  await page.getByRole('button', { name: 'Unirse a liga privada' }).click()
  const modal = page.getByRole('dialog', { name: 'Unirse a liga privada' })
  await expect(modal).toBeVisible()
  return modal
}

async function mock_by_code(page, fulfill) {
  const requests = []
  await page.route('**/api/leagues/by-code/*', async (route) => {
    requests.push({
      url: route.request().url(),
      authorization: route.request().headers().authorization,
    })
    await route.fulfill(fulfill(requests.length))
  })
  return requests
}

const lobby_navigation = (page) =>
  page.waitForEvent('framenavigated', {
    predicate: (frame) => new URL(frame.url()).pathname === `/league/${LEAGUE_ID}/waiting`,
  })

async function fill_team(page) {
  const selects = page.locator('.slot-card').getByRole('combobox')
  for (let index = 0; index < players.length; index += 1) {
    await selects.nth(index * 2).selectOption({ label: players[index].name })
    await selects.nth(index * 2 + 1).selectOption({ label: behaviors[0].name })
  }
}

test('joining a private league goes from the code to the password and the squad', async ({ page }) => {
  const by_code = await mock_by_code(page, () => ({ json: private_league }))
  await page.route('**/api/leagues/*', (route) => route.fulfill({ json: private_league }))
  const joins = []
  await page.route('**/api/leagues/*/join', async (route) => {
    joins.push({
      url: route.request().url(),
      authorization: route.request().headers().authorization,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      json: { enrollmentId: 'enrollment-1', clubId: session.club_id, leagueId: LEAGUE_ID },
    })
  })
  const modal = await open_modal(page)

  await modal.getByLabel('Código de la liga').fill(`  ${CODE} `)
  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await expect(page).toHaveURL(`/ligas/${LEAGUE_ID}/unirse`)
  expect(by_code).toHaveLength(1)
  expect(by_code[0].url).toMatch(new RegExp(`/api/leagues/by-code/${CODE}$`))
  expect(by_code[0].authorization).toBe(`Bearer ${session.access_token}`)

  await expect(page.getByRole('heading', { name: 'Liga Privada' })).toBeVisible()
  await expect(page.getByText('3 de 4')).toBeVisible()
  await fill_team(page)
  const confirm = page.getByRole('button', { name: 'Confirmar inscripción' })
  await expect(confirm).toBeDisabled()
  await page.getByLabel('Contraseña de la liga').fill('secreta')
  const to_lobby = lobby_navigation(page)
  await confirm.click()

  await to_lobby
  expect(joins).toHaveLength(1)
  expect(joins[0].url).toMatch(new RegExp(`/api/leagues/${LEAGUE_ID}/join$`))
  expect(joins[0].authorization).toBe(`Bearer ${session.access_token}`)
  expect(joins[0].body).toEqual({
    titulares: selection_of(players.slice(0, 3)),
    suplentes: selection_of(players.slice(3)),
    password: 'secreta',
  })
})

test('an enrolled club goes from the code straight to the lobby', async ({ page }) => {
  await mock_by_code(page, () => ({ json: { ...private_league, isEnrolled: true } }))
  const details = []
  await page.route('**/api/leagues/*', (route) => {
    details.push(route.request().url())
    return route.fulfill({ json: private_league })
  })
  const modal = await open_modal(page)

  await modal.getByLabel('Código de la liga').fill(CODE)
  const to_lobby = lobby_navigation(page)
  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await to_lobby
  expect(details).toHaveLength(0)
})

test('an unknown code is reported in the modal and another one can be entered', async ({ page }) => {
  await mock_by_code(page, (attempt) => (attempt === 1 ? not_found : { json: private_league }))
  await page.route('**/api/leagues/*', (route) => route.fulfill({ json: private_league }))
  const modal = await open_modal(page)

  await modal.getByLabel('Código de la liga').fill('malo1234')
  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await expect(modal.getByRole('alert')).toHaveText(
    'No hay ninguna liga con ese código. Revisalo e intentá de nuevo.'
  )
  await expect(page).toHaveURL('/home')

  await modal.getByLabel('Código de la liga').fill(CODE)
  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await expect(page).toHaveURL(`/ligas/${LEAGUE_ID}/unirse`)
})

test('an empty code does not reach the backend', async ({ page }) => {
  const by_code = await mock_by_code(page, () => not_found)
  const modal = await open_modal(page)

  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await expect(modal.getByRole('alert')).toHaveText('Ingresá el código de la liga.')
  expect(by_code).toHaveLength(0)
})

test('the modal can be closed with Cancelar and with Escape, and opens empty again', async ({ page }) => {
  const modal = await open_modal(page)

  await modal.getByLabel('Código de la liga').fill(CODE)
  await modal.getByRole('button', { name: 'Cancelar' }).click()
  await expect(modal).toHaveCount(0)
  await expect(page).toHaveURL('/home')

  await page.getByRole('button', { name: 'Unirse a liga privada' }).click()
  await expect(modal.getByLabel('Código de la liga')).toHaveValue('')

  await page.keyboard.press('Escape')
  await expect(modal).toHaveCount(0)
})

test('a 401 while searching clears the session and goes to the login', async ({ page }) => {
  await mock_by_code(page, () => ({
    status: 401,
    json: { detail: 'Sesión inválida o vencida', error_code: 'UNAUTHORIZED' },
  }))
  const modal = await open_modal(page)

  await modal.getByLabel('Código de la liga').fill(CODE)
  await modal.getByRole('button', { name: 'Buscar liga' }).click()

  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => localStorage.getItem('futbot.session'))).toBeNull()
})
