import { expect, test } from './fixtures.js'

const session = {
  expires_at: Math.floor(Date.now() / 1000) + 300,
  access_token: 'token-simulado',
  refresh_token: 'refresh-simulado',
  club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd',
}

const LEAGUE_ID = '33333333-3333-4333-8333-333333333333'
const JOIN_URL = `/ligas/${LEAGUE_ID}/unirse`

const players = ['Ana', 'Beto', 'Carla', 'Dani', 'Eva', 'Fito'].map((name) => ({
  id: `player-${name.toLowerCase()}`,
  name,
}))

const behaviors = [
  { id: 'behavior-front', name: 'Delantero' },
  { id: 'behavior-defense', name: 'Defensa' },
]

const starters = ['Ana', 'Beto', 'Carla']
const substitutes = ['Dani', 'Eva', 'Fito']
const team = {
  Ana: 'Delantero',
  Beto: 'Defensa',
  Carla: 'Delantero',
  Dani: 'Defensa',
  Eva: 'Delantero',
  Fito: 'Defensa',
}

const selection_of = (names) =>
  names.map((name) => ({
    playerId: players.find((player) => player.name === name).id,
    behaviorId: behaviors.find((behavior) => behavior.name === team[name]).id,
  }))

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

let listed_leagues

test.beforeEach(async ({ page }) => {
  listed_leagues = []
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } })
  )
  await page.route('**/api/players', (route) => route.fulfill({ json: players }))
  await page.route('**/api/behaviors', (route) => route.fulfill({ json: behaviors }))
  await page.routeWebSocket(/\/ws\/leagues$/, (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type !== 'auth') return
      ws.send(JSON.stringify({ type: 'leagues', name: '', leagues: listed_leagues }))
    })
  })
})

async function seed_session(page) {
  await page.goto('/login')
  await page.evaluate(
    (value) => localStorage.setItem('futbot.session', JSON.stringify(value)),
    session
  )
}

async function mock_detail(page, json) {
  await page.route('**/api/leagues/*', (route) => route.fulfill({ json }))
}

async function mock_join(page, status, json) {
  const requests = []
  await page.route('**/api/leagues/*/join', async (route) => {
    const request = route.request()
    requests.push({
      method: request.method(),
      url: request.url(),
      authorization: request.headers().authorization,
      body: request.postDataJSON(),
    })
    await route.fulfill({ status, json })
  })
  return requests
}

async function open_join_page(page) {
  await seed_session(page)
  await page.goto(JOIN_URL)
  await expect(page.getByRole('heading', { name: 'Liga del Barrio' })).toBeVisible()
}

const slot = (page, group, index) =>
  page.locator('.slot-card').filter({ hasText: `${group} ${index + 1}` })

async function fill_team(page) {
  for (const [group, names] of [['Titular', starters], ['Suplente', substitutes]]) {
    for (let index = 0; index < names.length; index += 1) {
      const selects = slot(page, group, index).getByRole('combobox')
      await selects.nth(0).selectOption({ label: names[index] })
      await selects.nth(1).selectOption({ label: team[names[index]] })
    }
  }
}

const confirm_button = (page) => page.getByRole('button', { name: 'Confirmar inscripción' })

const lobby_navigation = (page) =>
  page.waitForEvent('framenavigated', {
    predicate: (frame) =>
      frame === page.mainFrame() && new URL(frame.url()).pathname === `/league/${LEAGUE_ID}/waiting`,
  })

test('the league list leads to the join page of the selected league', async ({ page }) => {
  listed_leagues = [
    { id: 'otra-liga', name: 'Copa Sur', participantsCount: 2, started: false, isPrivate: false },
    { id: LEAGUE_ID, name: 'Liga del Barrio', participantsCount: 5, started: false, isPrivate: false },
  ]
  await mock_detail(page, detail())
  await seed_session(page)
  await page.goto('/leagues')

  await page
    .getByRole('listitem')
    .filter({ hasText: 'Liga del Barrio' })
    .getByRole('button', { name: 'Seleccionar', exact: true })
    .click()
  await page.getByRole('button', { name: 'Unirse a Liga', exact: true }).click()

  await expect(page).toHaveURL(JOIN_URL)
  await expect(page.getByRole('heading', { name: 'Unirse a liga', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Liga del Barrio' })).toBeVisible()
})

test('joining sends the POST with the token and the squad, then goes to the lobby', async ({ page }) => {
  await mock_detail(page, detail())
  const requests = await mock_join(page, 200, {
    enrollmentId: 'enrollment-1',
    clubId: session.club_id,
    leagueId: LEAGUE_ID,
  })
  await open_join_page(page)
  await expect(page.getByText('3 de 8')).toBeVisible()

  await expect(confirm_button(page)).toBeDisabled()
  await fill_team(page)
  const to_lobby = lobby_navigation(page)
  await confirm_button(page).click()

  await to_lobby
  expect(requests).toHaveLength(1)
  expect(requests[0].method).toBe('POST')
  expect(requests[0].url).toMatch(new RegExp(`/api/leagues/${LEAGUE_ID}/join$`))
  expect(requests[0].authorization).toBe(`Bearer ${session.access_token}`)
  expect(requests[0].body).toEqual({
    titulares: selection_of(starters),
    suplentes: selection_of(substitutes),
  })
})

test('a private league asks for its password and lets the user fix a wrong one', async ({ page }) => {
  await mock_detail(page, detail({ isPrivate: true }))
  const passwords = []
  await page.route('**/api/leagues/*/join', async (route) => {
    const { password } = route.request().postDataJSON()
    passwords.push(password)
    await route.fulfill(
      password === 'secreta'
        ? { json: { enrollmentId: 'enrollment-1', clubId: session.club_id, leagueId: LEAGUE_ID } }
        : { status: 400, json: { detail: 'La contraseña de la liga es incorrecta', error_code: 'WRONG_LEAGUE_PASSWORD' } }
    )
  })
  await open_join_page(page)

  await fill_team(page)
  await expect(confirm_button(page)).toBeDisabled()
  const password_field = page.getByLabel('Contraseña de la liga')
  await password_field.fill('otra')
  await confirm_button(page).click()

  const notice = page.getByRole('dialog', { name: 'Contraseña incorrecta' })
  await notice.getByRole('button', { name: 'Corregir contraseña' }).click()
  await expect(password_field).toBeFocused()

  await password_field.fill('secreta')
  const to_lobby = lobby_navigation(page)
  await confirm_button(page).click()

  await to_lobby
  expect(passwords).toEqual(['otra', 'secreta'])
})

test('a full league is reported without offering the squad selector', async ({ page }) => {
  await mock_detail(page, detail({ enrolledClubs: 8 }))
  await open_join_page(page)

  await expect(page.getByRole('alert')).toContainText('La liga está completa: ya no es posible unirse.')
  await expect(page.locator('.slot-card')).toHaveCount(0)
})

test('LEAGUE_FULL on confirm informs that the league is complete', async ({ page }) => {
  await mock_detail(page, detail())
  await mock_join(page, 400, {
    detail: 'La liga no tiene cupos disponibles',
    error_code: 'LEAGUE_FULL',
  })
  await open_join_page(page)

  await fill_team(page)
  await confirm_button(page).click()

  const dialog = page.getByRole('dialog', { name: 'Liga completa' })
  await expect(dialog).toContainText('La liga está completa: ya no es posible unirse.')
  await dialog.getByRole('button', { name: 'Volver al menú' }).click()
  await expect(page).toHaveURL('/home')
})

test('an enrolled club goes straight to the lobby', async ({ page }) => {
  await mock_detail(page, detail({ isEnrolled: true }))
  await seed_session(page)
  const to_lobby = lobby_navigation(page)

  await page.goto(JOIN_URL)

  await to_lobby
})

test('a 401 on confirm clears the session and goes to the login', async ({ page }) => {
  await mock_detail(page, detail())
  await mock_join(page, 401, { detail: 'Sesión inválida o vencida', error_code: 'UNAUTHORIZED' })
  await open_join_page(page)

  await fill_team(page)
  await confirm_button(page).click()

  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => localStorage.getItem('futbot.session'))).toBeNull()
})

test('without a session the join page goes to the login', async ({ page }) => {
  await page.goto(JOIN_URL)

  await expect(page).toHaveURL('/login')
})
