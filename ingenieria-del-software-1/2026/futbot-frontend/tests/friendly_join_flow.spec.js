import { expect, test } from '@playwright/test'

const session = { expires_at: Math.floor(Date.now() / 1000) + 300, access_token: 'token-simulado', refresh_token: 'refresh-simulado', club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd' }

const WS_URL = /\/ws\/friendly-rooms\/public$/
const UNAVAILABLE = { detail: 'La sala ya no está disponible.', error_code: 'ROOM_NOT_AVAILABLE' }

const rooms = [
  { roomId: 'room-1', status: 'waitingGuest', homeClub: 'club-a', homeClubName: 'Club Atlético Norte', createdAt: '2026-11-05T15:30:00Z' },
  { roomId: 'room-2', status: 'waitingGuest', homeClub: 'club-b', homeClubName: 'Racing del Sur', createdAt: '2026-11-04T18:45:00Z' },
]
const players = Array.from({ length: 7 }, (_, i) => ({ id: `player-${i + 1}`, name: `Jugador ${i + 1}`, isPlaying: false }))
const behaviors = [{ id: 'behavior-front', name: 'Delantero' }, { id: 'behavior-defense', name: 'Defensa' }]

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 204 }))
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } }))
  await page.route('**/api/players', (route) => route.fulfill({ json: players }))
  await page.route('**/api/behaviors', (route) => route.fulfill({ json: behaviors }))
})

// --- Ayudas ---

async function seed_session(page) {
  await page.goto('/login')
  await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), session)
}

// Simula /ws/friendly-rooms/public: cada conexión nueva recibe el listado actual de mock.data
async function mock_public_socket(page, initial = rooms) {
  const mock = { data: initial }
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === 'auth') ws.send(JSON.stringify({ type: 'rooms', rooms: mock.data }))
    })
  })
  return mock
}

// Registra los POST de unión; `respond(n, route)` decide la respuesta del n-ésimo intento
async function mock_join(page, respond) {
  const joins = []
  await page.route('**/api/friendly/rooms/*/join', async (route) => {
    const request = route.request()
    joins.push({ url: request.url(), headers: request.headers(), body: request.postDataJSON() })
    await respond(joins.length, route)
  })
  return joins
}

const room_card = (page, club) =>
  page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: club, exact: true }) })

async function pick_room(page, club) {
  await room_card(page, club).getByRole('button', { name: /^Unirse/ }).click()
  await expect(page).toHaveURL('/friendly/join')
}

async function open_list(page) {
  await seed_session(page)
  await page.goto('/friendly')
  await expect(page.getByRole('heading', { name: 'Amistosos disponibles' })).toBeVisible()
}

// AJUSTAR a la interfaz real de SquadSelector: 6 puestos, cada uno con un select de jugador y uno de comportamiento
async function fill_squad(page) {
  const selects = page.getByRole('combobox')
  await expect(selects).toHaveCount(12)
  for (let slot = 0; slot < 6; slot++) {
    await selects.nth(slot * 2).selectOption({ index: slot + 1 })      // jugador distinto en cada puesto
    await selects.nth(slot * 2 + 1).selectOption({ index: 1 })         // comportamiento
  }
}

const confirm_button = (page) => page.getByRole('button', { name: /^(Confirmar y unirse|Uniéndote…)$/ })

// --- Unirse sin código ---

test('el flujo de unirse no pide ningún código y envía solo titulares y suplentes por la URL de la sala', async ({ page }) => {
  await mock_public_socket(page)
  const joins = await mock_join(page, (_n, route) =>
    route.fulfill({ json: { roomId: 'room-2', status: 'readyToStart', awayClub: session.club_id } }))
  await open_list(page)
  await pick_room(page, 'Racing del Sur')
  await expect(page.getByText(/código/i)).toHaveCount(0)
  await expect(page.getByRole('textbox')).toHaveCount(0)
  await fill_squad(page)
  await confirm_button(page).click()
  await expect(page).toHaveURL('/amistosos/room-2/sala')
  expect(joins).toHaveLength(1)
  expect(joins[0].url).toMatch(/\/api\/friendly\/rooms\/room-2\/join$/)
  expect(joins[0].headers.authorization).toBe(`Bearer ${session.access_token}`)
  expect(Object.keys(joins[0].body).sort()).toEqual(['suplentes', 'titulares'])
  expect(joins[0].body.titulares).toHaveLength(3)
  expect(joins[0].body.suplentes).toHaveLength(3)
})

// --- Sala ocupada por otro club (conflicto de concurrencia) ---

test('si otro club ocupa la sala (409) muestra la alerta, saca la sala del listado y conserva la plantilla', async ({ page }) => {
  const mock = await mock_public_socket(page)
  const joins = await mock_join(page, (n, route) => (
    n === 1
      ? route.fulfill({ status: 409, json: UNAVAILABLE })
      : route.fulfill({ json: { roomId: 'room-2', status: 'readyToStart', awayClub: session.club_id } })
  ))
  await open_list(page)
  await pick_room(page, 'Club Atlético Norte')
  await fill_squad(page)

  mock.data = [rooms[1]]                      // mientras tanto, el servidor ya no lista la sala ocupada
  await confirm_button(page).click()

  const alert = page.getByRole('dialog')
  await expect(alert.getByRole('heading', { name: 'La sala ya no está disponible' })).toBeVisible()
  await expect(alert.getByRole('alert')).toContainText('tu plantilla se conserva')
  expect(joins).toHaveLength(1)

  await alert.getByRole('button', { name: 'Volver al listado' }).click()
  await expect(page).toHaveURL('/friendly')
  await expect(room_card(page, 'Club Atlético Norte')).toHaveCount(0)       // el listado se refrescó solo
  await expect(room_card(page, 'Racing del Sur')).toBeVisible()
  await expect(page.getByText('Tu plantilla se conserva')).toBeVisible()

  await pick_room(page, 'Racing del Sur')
  await expect(confirm_button(page)).toBeEnabled()                           // la plantilla sigue completa
  await confirm_button(page).click()
  await expect(page).toHaveURL('/amistosos/room-2/sala')
  expect(joins).toHaveLength(2)
  expect(joins[1].body).toEqual(joins[0].body)                               // misma plantilla, sin volver a elegirla
})

test('el 409 no se confunde con una selección inválida y no vacía la plantilla en pantalla', async ({ page }) => {
  await mock_public_socket(page)
  await mock_join(page, (_n, route) => route.fulfill({ status: 409, json: UNAVAILABLE }))
  await open_list(page)
  await pick_room(page, 'Club Atlético Norte')
  await fill_squad(page)
  await confirm_button(page).click()
  const alert = page.getByRole('dialog')
  await expect(alert.getByRole('heading', { name: 'La sala ya no está disponible' })).toBeVisible()
  await expect(alert.getByRole('button', { name: 'Volver a seleccionar' })).toHaveCount(0)   // no ofrece reiniciar
  await expect(alert.getByRole('button', { name: 'Volver al listado' })).toBeVisible()
})

test('si la sala ya no existe (404) también avisa y permite volver al listado', async ({ page }) => {
  await mock_public_socket(page)
  await mock_join(page, (_n, route) => route.fulfill({ status: 404, json: { detail: 'Sala no encontrada.', error_code: 'NOT_FOUND' } }))
  await open_list(page)
  await pick_room(page, 'Club Atlético Norte')
  await fill_squad(page)
  await confirm_button(page).click()
  const alert = page.getByRole('dialog')
  await expect(alert.getByRole('heading', { name: 'La sala ya no está disponible' })).toBeVisible()
  await alert.getByRole('button', { name: 'Volver al listado' }).click()
  await expect(page).toHaveURL('/friendly')
})

test('Escape no cierra la alerta de sala ocupada: hay que usar su acción', async ({ page }) => {
  await mock_public_socket(page)
  await mock_join(page, (_n, route) => route.fulfill({ status: 409, json: UNAVAILABLE }))
  await open_list(page)
  await pick_room(page, 'Club Atlético Norte')
  await fill_squad(page)
  await confirm_button(page).click()
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'La sala ya no está disponible' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'La sala ya no está disponible' })).toBeVisible()
})