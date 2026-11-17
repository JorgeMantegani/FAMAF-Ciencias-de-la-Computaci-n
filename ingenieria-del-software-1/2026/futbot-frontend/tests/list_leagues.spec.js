import { expect, test } from '@playwright/test'

const session = { expires_at: Math.floor(Date.now() / 1000) + 300, access_token: 'token-simulado', refresh_token: 'refresh-simulado', club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd' }

const WS_URL = /\/ws\/leagues$/

const leagues = [
  { id: 'league-norte', name: 'Liga Norte', participantsCount: 12, started: false, isPrivate: false },
  { id: 'league-sur', name: 'Copa Sur', participantsCount: 1, started: true, isPrivate: false },
  { id: 'league-centro', name: 'Liga del Centro', participantsCount: 0, started: false, isPrivate: false },
]
const new_league = { id: 'league-nueva', name: 'Liga Nueva', participantsCount: 0, started: false, isPrivate: false }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 204 }))
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } }))
})

// --- Ayudas ---

async function stored_session(page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem('futbot.session')))
}

async function seed_session(page) {
  await page.goto('/login')
  await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), session)
}

function filter_leagues(all, name) {
  const needle = name.trim().toLowerCase()
  return needle ? all.filter((league) => league.name.toLowerCase().includes(needle)) : all
}

// Simula /ws/leagues como el servidor: responde al auth y a cada búsqueda con el listado filtrado.
// mock.received guarda lo que envió la pantalla; mock.push(all) simula un cambio en el servidor.
async function mock_leagues_socket(page, initial = leagues) {
  const mock = { all: initial, received: [], connections: [] }
  const send_list = (connection) => connection.ws.send(JSON.stringify({
    type: 'leagues', name: connection.name, leagues: filter_leagues(mock.all, connection.name),
  }))
  await page.route('**/api/leagues/*/standings', (route) => route.fulfill({ json: [] }))
  await page.routeWebSocket(WS_URL, (ws) => {
    const connection = { ws, name: '' }
    mock.connections.push(connection)
    ws.onMessage((raw) => {
      const message = JSON.parse(String(raw))
      mock.received.push(message)
      if (message.type === 'search') connection.name = message.name.trim()
      if (message.type === 'auth' || message.type === 'search') send_list(connection)
    })
  })
  mock.push = (all) => {
    mock.all = all
    send_list(mock.connections.at(-1))
  }
  mock.searches = () => mock.received.filter((message) => message.type === 'search')
  return mock
}

async function open_leagues(page) {
  await seed_session(page)
  await page.goto('/leagues')
  await expect(page.getByRole('heading', { name: 'Ligas disponibles' })).toBeVisible()
}

const league_card = (page, name) =>
  page.getByRole('listitem').filter({ has: page.getByRole('heading', { name, exact: true }) })

async function search_for(page, text) {
  await page.getByLabel('Buscar por nombre').fill(text)
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
}

// --- Acceso ---

test('el menú ofrece ver las ligas y lleva al listado', async ({ page }) => {
  await mock_leagues_socket(page)
  await seed_session(page)
  await page.goto('/home')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  await page.getByRole('link', { name: /ver ligas/i }).click()
  await expect(page).toHaveURL('/leagues')
  await expect(page.getByRole('heading', { name: 'Ligas disponibles' })).toBeVisible()
})

test('sin sesión, el listado lleva al login', async ({ page }) => {
  await page.goto('/leagues')
  await expect(page).toHaveURL('/login')
})

// --- Listado por WebSocket ---

test('al entrar abre el canal, se autentica con el token y toma el listado inicial', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(league_card(page, 'Liga Norte')).toBeVisible()
  expect(mock.received[0]).toEqual({ type: 'auth', token: session.access_token })
  expect(mock.searches()).toHaveLength(0)    // sin filtro, no hace falta pedir nada más
})

test('muestra nombre, participantes y estado de cada liga, sin indicar si es pública o privada', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await expect(league_card(page, 'Liga Norte')).toContainText('12 participantes')
  await expect(league_card(page, 'Liga Norte')).toContainText('Sin iniciar')
  await expect(league_card(page, 'Copa Sur')).toContainText('1 participante')
  await expect(league_card(page, 'Copa Sur')).not.toContainText('1 participantes')
  await expect(league_card(page, 'Copa Sur')).toContainText('Iniciada')
  await expect(league_card(page, 'Liga del Centro')).toContainText('0 participantes')
  await expect(page.getByText('3 ligas', { exact: true })).toBeVisible()
  await expect(page.getByText('Privada')).toHaveCount(0)
  await expect(page.getByText('Pública')).toHaveCount(0)
})

test('muestra el estado de carga hasta recibir el listado', async ({ page }) => {
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage(async (raw) => {
      if (JSON.parse(String(raw)).type !== 'auth') return
      await gate
      ws.send(JSON.stringify({ type: 'leagues', name: '', leagues }))
    })
  })
  await open_leagues(page)
  await expect(page.getByRole('status')).toContainText('Cargando ligas')
  release()
  await expect(league_card(page, 'Liga Norte')).toBeVisible()
})

test('sin ligas informa que no hay disponibles', async ({ page }) => {
  await mock_leagues_socket(page, [])
  await open_leagues(page)
  await expect(page.getByText('Todavía no hay ligas disponibles.')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(0)
})

test('no hay forma de actualizar el listado a mano', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(league_card(page, 'Liga Norte')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Actualizar' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reintentar' })).toHaveCount(0)
})

// --- Búsqueda ---

test('buscar envía la búsqueda por el canal y actualiza el listado', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await search_for(page, 'liga')
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(league_card(page, 'Liga Norte')).toBeVisible()
  await expect(league_card(page, 'Liga del Centro')).toBeVisible()
  await expect(league_card(page, 'Copa Sur')).toHaveCount(0)
  await expect(page.getByText('2 ligas para "liga"', { exact: true })).toBeVisible()
  expect(mock.searches().at(-1)).toEqual({ type: 'search', name: 'liga' })
})

test('la búsqueda ignora los espacios de los costados', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await search_for(page, '  sur  ')
  await expect(league_card(page, 'Copa Sur')).toBeVisible()
  expect(mock.searches().at(-1)).toEqual({ type: 'search', name: 'sur' })
})

test('buscar con Enter también filtra', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await page.getByLabel('Buscar por nombre').fill('copa')
  await page.getByLabel('Buscar por nombre').press('Enter')
  await expect(page.getByRole('listitem')).toHaveCount(1)
})

test('una búsqueda sin coincidencias informa al usuario', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await search_for(page, 'zzz')
  await expect(page.getByText('No hay ligas que coincidan con "zzz".')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(0)
})

test('Limpiar vuelve a mostrar todas las ligas', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await search_for(page, 'sur')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await page.getByRole('button', { name: 'Limpiar', exact: true }).click()
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await expect(page.getByLabel('Buscar por nombre')).toHaveValue('')
  expect(mock.searches().at(-1)).toEqual({ type: 'search', name: '' })
})

test('la búsqueda con tildes y ñ se envía sin alterar', async ({ page }) => {
  const mock = await mock_leagues_socket(page, [{ ...new_league, id: 'league-nandu', name: 'Liga Ñandú' }])
  await open_leagues(page)
  await search_for(page, 'ÑANDÚ')
  await expect(league_card(page, 'Liga Ñandú')).toBeVisible()
  expect(mock.searches().at(-1)).toEqual({ type: 'search', name: 'ÑANDÚ' })
})

// --- Actualización en vivo ---

test('el listado se actualiza solo cuando el servidor avisa un cambio', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  mock.push([...leagues, new_league])
  await expect(league_card(page, 'Liga Nueva')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(4)
})

test('los cambios respetan la búsqueda aplicada', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await search_for(page, 'sur')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  mock.push([...leagues, { ...new_league, name: 'Torneo Sur' }, { ...new_league, id: 'league-oeste', name: 'Liga Oeste' }])
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(league_card(page, 'Torneo Sur')).toBeVisible()
  await expect(league_card(page, 'Liga Oeste')).toHaveCount(0)
})

test('un cambio en la cantidad de participantes se ve sin recargar', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(league_card(page, 'Liga Norte')).toContainText('12 participantes')
  mock.push(leagues.map((league) => (league.id === 'league-norte' ? { ...league, participantsCount: 13 } : league)))
  await expect(league_card(page, 'Liga Norte')).toContainText('13 participantes')
})

test('si se corta la conexión avisa, conserva el listado y se reconecta sola', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  mock.connections.at(-1).ws.close({ code: 1001 })
  await expect(page.getByRole('alert')).toContainText('Sin conexión con el servidor')
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await expect(page.getByRole('alert')).toHaveCount(0)    // reconectó
  mock.push([...leagues, new_league])
  await expect(page.getByRole('listitem')).toHaveCount(4)
})

test('si el servidor rechaza el token (4401) borra la sesión y lleva al login', async ({ page }) => {
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage(() => ws.close({ code: 4401, reason: 'No autorizado' }))
  })
  await seed_session(page)
  await page.goto('/leagues')
  await expect(page).toHaveURL('/login')
  expect(await stored_session(page)).toBeNull()
})

// --- Selección ---

test('seleccionar una liga la resalta y la muestra como elegida', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  const button = league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionada', exact: true })
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Liga seleccionada: Liga Norte' })).toBeVisible()
})

test('solo se puede elegir una liga a la vez y volver a tocarla la quita', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  await league_card(page, 'Copa Sur').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Liga seleccionada: Copa Sur' })).toBeVisible()
  await expect(league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true })).toBeVisible()
  await league_card(page, 'Copa Sur').getByRole('button', { name: 'Seleccionada', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Liga seleccionada/ })).toHaveCount(0)
})

test('Quitar selección descarta la liga elegida', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  await page.getByRole('button', { name: 'Quitar selección', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Liga seleccionada/ })).toHaveCount(0)
  await expect(league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true })).toBeVisible()
})

test('la liga elegida se conserva al cambiar la búsqueda', async ({ page }) => {
  await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  await search_for(page, 'copa')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Liga seleccionada: Liga Norte' })).toBeVisible()
})

test('un cambio en vivo refresca los datos de la liga seleccionada', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  mock.push(leagues.map((league) => (league.id === 'league-norte' ? { ...league, participantsCount: 13 } : league)))
  const panel = page.getByRole('region', { name: 'Liga seleccionada: Liga Norte' })
  await expect(panel).toContainText('13 participantes')
})

test('si la liga seleccionada desaparece del listado, se descarta la selección', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await league_card(page, 'Liga Norte').getByRole('button', { name: 'Seleccionar', exact: true }).click()
  mock.push(leagues.filter((league) => league.id !== 'league-norte'))
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(page.getByRole('heading', { name: /Liga seleccionada/ })).toHaveCount(0)
})

test('si la sesión se vence con el canal cortado, no queda reintentando: lleva al login', async ({ page }) => {
  const mock = await mock_leagues_socket(page)
  await open_leagues(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await page.evaluate(() => localStorage.removeItem('futbot.session'))    // la sesión desaparece
  mock.connections.at(-1).ws.close({ code: 1001 })                        // y se corta la conexión
  await expect(page).toHaveURL('/login')
})

test('un 4401 no borra una sesión nueva abierta en otra pestaña', async ({ page }) => {
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage(async () => {
      // mientras el canal se cierra, otra pestaña ya inició sesión de nuevo
      await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), {
        ...session, access_token: 'token-nuevo', refresh_token: 'refresh-nuevo',
      })
      ws.close({ code: 4401, reason: 'No autorizado' })
    })
  })
  await seed_session(page)
  await page.goto('/leagues')
  await expect(page).toHaveURL(/\/(login|home)$/)
  const stored = await stored_session(page)
  expect(stored?.refresh_token).toBe('refresh-nuevo')                     // la sesión nueva se conserva
})