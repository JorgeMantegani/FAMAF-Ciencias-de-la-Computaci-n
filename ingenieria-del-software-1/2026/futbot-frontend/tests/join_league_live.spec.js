import { expect, test } from './fixtures.js'

const session = {
  expires_at: Math.floor(Date.now() / 1000) + 300,
  access_token: 'token-simulado',
  refresh_token: 'refresh-simulado',
  club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd',
}

const LEAGUE_ID = '33333333-3333-4333-8333-333333333333'

const players = ['Ana', 'Beto', 'Carla', 'Dani', 'Eva', 'Fito'].map((name) => ({
  id: `player-${name.toLowerCase()}`,
  name,
}))

const behaviors = [{ id: 'behavior-front', name: 'Delantero' }]

const detail = (overrides = {}) => ({
  leagueId: LEAGUE_ID,
  name: 'Liga del Barrio',
  isPrivate: false,
  status: 'waitingGuest',
  minClubs: 3,
  maxClubs: 8,
  enrolledClubs: 5,
  matchDurationMinutes: 10,
  isEnrolled: false,
  mySquad: null,
  ...overrides,
})

const listed = (participantsCount, overrides = {}) => ({
  id: LEAGUE_ID,
  name: 'Liga del Barrio',
  participantsCount,
  started: false,
  isPrivate: false,
  ...overrides,
})

async function mock_leagues_socket(page, leagues) {
  const mock = { leagues, socket: null }
  const send = () =>
    mock.socket.send(JSON.stringify({ type: 'leagues', name: '', leagues: mock.leagues }))

  await page.routeWebSocket(/\/ws\/leagues$/, (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type !== 'auth') return
      mock.socket = ws
      send()
    })
  })

  mock.push = async (next) => {
    await expect.poll(() => mock.socket !== null).toBe(true)
    mock.leagues = next
    send()
  }
  return mock
}

async function open_join_page(page, json = detail()) {
  await page.route('**/api/leagues/*', (route) => route.fulfill({ json }))
  await page.goto('/login')
  await page.evaluate(
    (value) => localStorage.setItem('futbot.session', JSON.stringify(value)),
    session
  )
  await page.goto(`/ligas/${LEAGUE_ID}/unirse`)
  await expect(page.getByRole('heading', { name: 'Liga del Barrio' })).toBeVisible()
}

async function fill_team(page) {
  const selects = page.locator('.slot-card').getByRole('combobox')
  for (let index = 0; index < players.length; index += 1) {
    await selects.nth(index * 2).selectOption({ label: players[index].name })
    await selects.nth(index * 2 + 1).selectOption({ label: behaviors[0].name })
  }
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/players', (route) => route.fulfill({ json: players }))
  await page.route('**/api/behaviors', (route) => route.fulfill({ json: behaviors }))
})

test('the free spots follow the league list until the league is full', async ({ page }) => {
  const socket = await mock_leagues_socket(page, [listed(5)])
  await open_join_page(page)
  await expect(page.getByText('3 de 8')).toBeVisible()

  await socket.push([listed(6)])
  await expect(page.getByText('2 de 8')).toBeVisible()
  await expect(page.locator('.slot-card')).toHaveCount(6)

  await socket.push([listed(8)])
  await expect(page.getByText('0 de 8')).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('La liga está completa: ya no es posible unirse.')
  await expect(page.locator('.slot-card')).toHaveCount(0)
})

test('a league that starts stops accepting clubs without reloading', async ({ page }) => {
  const socket = await mock_leagues_socket(page, [listed(5)])
  await open_join_page(page)
  await expect(page.locator('.slot-card')).toHaveCount(6)

  await socket.push([listed(5, { started: true })])

  await expect(page.getByRole('alert')).toContainText('La liga ya no admite inscripciones.')
  await expect(page.getByText('En juego')).toBeVisible()
  await expect(page.locator('.slot-card')).toHaveCount(0)
})

test('taking the last spot goes to the lobby without reporting a full league', async ({ page }) => {
  const socket = await mock_leagues_socket(page, [listed(7)])
  await open_join_page(page, detail({ enrolledClubs: 7 }))
  await page.route('**/api/leagues/*/join', async (route) => {
    await socket.push([listed(8)])
    await expect(page.getByText('0 de 8')).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await route.fulfill({
      json: { enrollmentId: 'enrollment-1', clubId: session.club_id, leagueId: LEAGUE_ID },
    })
  })

  await fill_team(page)
  const to_lobby = page.waitForEvent('framenavigated', {
    predicate: (frame) => new URL(frame.url()).pathname === `/league/${LEAGUE_ID}/waiting`,
  })
  await page.getByRole('button', { name: 'Confirmar inscripción' }).click()

  await to_lobby
})
