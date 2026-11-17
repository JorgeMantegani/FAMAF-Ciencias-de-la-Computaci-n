import { expect, test } from '@playwright/test'

const session = { expires_at: Math.floor(Date.now() / 1000) + 300, access_token: 'token-simulado', refresh_token: 'refresh-simulado', club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd' }

const WS_URL = /\/ws\/friendly-rooms\/public$/

test.use({ locale: 'es-AR', timezoneId: 'America/Argentina/Cordoba' })   // fechas deterministas: UTC-3

const rooms = [
  { roomId: 'room-1', status: 'waitingGuest', homeClub: 'club-a', homeClubName: 'Club Atlético Norte', createdAt: '2026-11-05T15:30:00' },
  { roomId: 'room-2', status: 'waitingGuest', homeClub: 'club-b', homeClubName: 'Racing del Sur', createdAt: '2026-11-04T18:45:00Z' },
]
const new_room = { roomId: 'room-3', status: 'waitingGuest', homeClub: 'club-c', homeClubName: 'Unión del Este', createdAt: '2026-11-05T16:00:00' }

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

// Simula /ws/friendly-rooms/public como el servidor: responde al auth con el listado.
// mock.received guarda lo que envió la pantalla; mock.push(data) simula un cambio en el servidor.
async function mock_rooms_socket(page, initial = rooms) {
  const mock = { data: initial, received: [], connections: [] }
  const send_list = (connection) => connection.ws.send(JSON.stringify({ type: 'rooms', rooms: mock.data }))
  await page.routeWebSocket(WS_URL, (ws) => {
    const connection = { ws }
    mock.connections.push(connection)
    ws.onMessage((raw) => {
      const message = JSON.parse(String(raw))
      mock.received.push(message)
      if (message.type === 'auth') send_list(connection)
    })
  })
  mock.push = (data) => {
    mock.data = data
    send_list(mock.connections.at(-1))
  }
  return mock
}

async function open_list(page) {
  await seed_session(page)
  await page.goto('/friendly')
  await expect(page.getByRole('heading', { name: 'Amistosos disponibles' })).toBeVisible()
}

const room_card = (page, club) =>
  page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: club, exact: true }) })

const search = (page) => page.getByLabel('Buscar por nombre del club')

// --- Acceso ---

test('el menú ofrece unirse a un amistoso y lleva al listado', async ({ page }) => {
  await mock_rooms_socket(page)
  await seed_session(page)
  await page.goto('/home')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  await page.getByRole('link', { name: 'Unirse a un amistoso', exact: true }).click()
  await expect(page).toHaveURL('/friendly')
  await expect(page.getByRole('heading', { name: 'Amistosos disponibles' })).toBeVisible()
})

test('sin sesión, el listado lleva al login', async ({ page }) => {
  await page.goto('/friendly')
  await expect(page).toHaveURL('/login')
})

// --- Listado por WebSocket ---

test('al entrar abre el canal y se autentica con el token', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(room_card(page, 'Club Atlético Norte')).toBeVisible()
  expect(mock.received[0]).toEqual({ type: 'auth', token: session.access_token })
})

test('muestra el club local, el estado y la fecha de creación de cada sala', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  const norte = room_card(page, 'Club Atlético Norte')
  await expect(norte).toContainText('Esperando rival')
  await expect(norte).toContainText(/12:30/)    // 15:30 UTC = 12:30 en Córdoba (sin "Z" se toma como UTC)
  await expect(norte.locator('time')).toHaveAttribute('datetime', '2026-11-05T15:30:00.000Z')
  const sur = room_card(page, 'Racing del Sur')
  await expect(sur).toContainText(/15:45/)      // 18:45 UTC = 15:45 en Córdoba
  await expect(sur.locator('time')).toHaveAttribute('datetime', '2026-11-04T18:45:00.000Z')
})

test('cada sala tiene su botón Unirse', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(page.getByRole('button', { name: /^Unirse a la sala de/ })).toHaveCount(2)
  await expect(room_card(page, 'Racing del Sur').getByRole('button', { name: 'Unirse a la sala de Racing del Sur' })).toBeVisible()
})

test('respeta el orden que manda el servidor (más recientes primero)', async ({ page }) => {
  await mock_rooms_socket(page, [new_room, ...rooms])
  await open_list(page)
  await expect(page.getByRole('listitem').getByRole('heading')).toHaveText(['Unión del Este', 'Club Atlético Norte', 'Racing del Sur'])
})

// --- Estados ---

test('muestra el estado de carga hasta recibir el listado', async ({ page }) => {
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage(async (raw) => {
      if (JSON.parse(String(raw)).type !== 'auth') return
      await gate
      ws.send(JSON.stringify({ type: 'rooms', rooms }))
    })
  })
  await open_list(page)
  await expect(page.getByRole('status')).toContainText('Cargando amistosos')
  release()
  await expect(room_card(page, 'Club Atlético Norte')).toBeVisible()
  await expect(page.getByText('Cargando amistosos')).toHaveCount(0)
})

test('sin salas muestra "No hay amistosos disponibles"', async ({ page }) => {
  await mock_rooms_socket(page, [])
  await open_list(page)
  await expect(page.getByText('No hay amistosos disponibles')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(0)
})

test('no hay botones para actualizar el listado a mano', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  await expect(room_card(page, 'Club Atlético Norte')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Actualizar' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reintentar' })).toHaveCount(0)
})

// --- Actualización en vivo ---

test('una sala nueva aparece sola cuando el servidor avisa', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(2)
  mock.push([new_room, ...rooms])
  await expect(room_card(page, 'Unión del Este')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(3)
})

test('una sala que se completa desaparece sola del listado', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(room_card(page, 'Racing del Sur')).toBeVisible()
  mock.push(rooms.filter((room) => room.roomId !== 'room-2'))
  await expect(room_card(page, 'Racing del Sur')).toHaveCount(0)
  await expect(page.getByRole('listitem')).toHaveCount(1)
})

test('cuando desaparece la última sala, muestra el estado vacío', async ({ page }) => {
  const mock = await mock_rooms_socket(page, [rooms[0]])
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(1)
  mock.push([])
  await expect(page.getByText('No hay amistosos disponibles')).toBeVisible()
})

test('si se corta la conexión avisa, conserva el listado y se reconecta sola', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(2)
  mock.connections.at(-1).ws.close({ code: 1001 })
  await expect(page.getByRole('alert')).toContainText('Sin conexión con el servidor')
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(page.getByRole('alert')).toHaveCount(0)    // reconectó
  mock.push([new_room, ...rooms])
  await expect(page.getByRole('listitem')).toHaveCount(3)
})

test('un mensaje con formato inválido no rompe la pantalla ni borra el listado', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(2)
  const { ws } = mock.connections.at(-1)
  ws.send('esto no es json')
  ws.send(JSON.stringify({ type: 'rooms', rooms: 'no es una lista' }))
  ws.send(JSON.stringify({ type: 'otra-cosa' }))
  await expect(page.getByRole('listitem')).toHaveCount(2)
})

test('si el servidor rechaza el token (4401) borra la sesión y lleva al login', async ({ page }) => {
  await page.routeWebSocket(WS_URL, (ws) => {
    ws.onMessage(() => ws.close({ code: 4401, reason: 'No autorizado' }))
  })
  await seed_session(page)
  await page.goto('/friendly')
  await expect(page).toHaveURL('/login')
  expect(await stored_session(page)).toBeNull()
})

test('si la sesión se vence con el canal cortado, no queda reintentando: lleva al login', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(2)
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
  await page.goto('/friendly')
  await expect(page).toHaveURL(/\/(login|home)$/)
  const stored = await stored_session(page)
  expect(stored?.refresh_token).toBe('refresh-nuevo')                     // la sesión nueva se conserva
})

// --- Unirse ---

test('Unirse lleva a la selección del equipo con la sala elegida', async ({ page }) => {
  await mock_rooms_socket(page)
  await page.route('**/api/players', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/behaviors/preprogrammed', (route) => route.fulfill({ json: [] }))
  await open_list(page)
  await room_card(page, 'Racing del Sur').getByRole('button', { name: /^Unirse/ }).click()
  await expect(page).toHaveURL('/friendly/join')
  await expect(page.getByText('Sala de Racing del Sur')).toBeVisible()
})

test('abrir la pantalla de unión sin haber elegido una sala vuelve al listado', async ({ page }) => {
  await mock_rooms_socket(page)
  await seed_session(page)
  await page.goto('/friendly/join')
  await expect(page).toHaveURL('/friendly')
  await expect(page.getByRole('heading', { name: 'Amistosos disponibles' })).toBeVisible()
})

// --- Buscador ---

test('filtra mientras se escribe, sin botón de buscar ni pedidos al servidor', async ({ page }) => {
  const mock = await mock_rooms_socket(page, [new_room, ...rooms])
  await open_list(page)
  await expect(page.getByRole('listitem')).toHaveCount(3)
  await search(page).pressSequentially('u')
  await expect(page.getByRole('listitem')).toHaveCount(3)      // "u" está en los tres nombres
  await search(page).pressSequentially('n')
  await expect(page.getByRole('listitem')).toHaveCount(1)      // "un" solo en "Unión del Este"
  await expect(room_card(page, 'Unión del Este')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buscar' })).toHaveCount(0)
  expect(mock.received).toEqual([{ type: 'auth', token: session.access_token }])   // nada más salió al servidor
})

test('ignora mayúsculas y los espacios de los costados', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  await search(page).fill('  ATLÉTICO  ')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await expect(room_card(page, 'Club Atlético Norte')).toBeVisible()
})

test('una búsqueda sin coincidencias informa al usuario', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  await search(page).fill('zzz')
  await expect(page.getByText('No hay amistosos que coincidan con "zzz".')).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(0)
})

test('Limpiar vuelve a mostrar todas las salas', async ({ page }) => {
  await mock_rooms_socket(page)
  await open_list(page)
  await search(page).fill('sur')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await expect(page.getByText('1 de 2 salas')).toBeVisible()
  await page.getByRole('button', { name: 'Limpiar', exact: true }).click()
  await expect(page.getByRole('listitem')).toHaveCount(2)
  await expect(search(page)).toHaveValue('')
})

test('los cambios en vivo respetan el filtro escrito', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await search(page).fill('sur')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  const sur_unido = { ...new_room, roomId: 'room-4', homeClubName: 'Sur Unido' }
  mock.push([new_room, sur_unido, ...rooms])
  await expect(page.getByRole('listitem')).toHaveCount(2)      // "Sur Unido" entra; "Unión del Este" no
  await expect(room_card(page, 'Sur Unido')).toBeVisible()
  await expect(room_card(page, 'Unión del Este')).toHaveCount(0)
  await expect(search(page)).toHaveValue('sur')                // el texto no se pierde
})

test('si el servidor se queda sin salas con un filtro activo, muestra el estado vacío general', async ({ page }) => {
  const mock = await mock_rooms_socket(page)
  await open_list(page)
  await search(page).fill('sur')
  mock.push([])
  await expect(page.getByText('No hay amistosos disponibles.')).toBeVisible()
})

test('Unirse desde una lista filtrada lleva a la sala correcta', async ({ page }) => {
  await mock_rooms_socket(page)
  await page.route('**/api/players', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/behaviors/preprogrammed', (route) => route.fulfill({ json: [] }))
  await open_list(page)
  await search(page).fill('sur')
  await room_card(page, 'Racing del Sur').getByRole('button', { name: /^Unirse/ }).click()
  await expect(page).toHaveURL('/friendly/join')
  await expect(page.getByText('Sala de Racing del Sur')).toBeVisible()
})