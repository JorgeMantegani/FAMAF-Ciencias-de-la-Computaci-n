import { expect, test } from './fixtures.js'

const session = { expires_at: Math.floor(Date.now() / 1000) + 300, access_token: 'token-simulado', refresh_token: 'refresh-simulado', club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd' }
test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/logout', async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${session.access_token}`)
    await route.fulfill({ status: 204 })
  })
  await page.route('**/api/auth/refresh', (route) => route.fulfill({ status: 401, json: { detail: 'Sesión vencida' } }))
  await page.route('**/api/auth/me', async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${session.access_token}`)
    await route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } })
  })
})

const credentials = { email: 'manager@example.com', password: ' Mi clave secreta ' }

async function fill_login(page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Contraseña', { exact: true }).fill(credentials.password)
}

async function stored_session(page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem('futbot.session')))
}

test('impide enviar campos vacíos y un email inválido', async ({ page }) => {
  const requests = []
  await page.route('**/api/auth/login', async (route) => {
    requests.push(route.request())
    await route.fulfill({ json: session })
  })
  await page.goto('/login')
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByLabel('Email')).toBeFocused()
  await page.getByLabel('Email').fill('manager@example.com')
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByLabel('Contraseña', { exact: true })).toBeFocused()
  await page.getByLabel('Email').fill('email-invalido')
  await page.getByLabel('Contraseña', { exact: true }).fill('clave')
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByLabel('Email')).toBeFocused()
  expect(requests).toHaveLength(0)
  expect(await stored_session(page)).toBeNull()
})

test('envía datos exactos, guarda la sesión y muestra éxito antes de ir a home', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().headers().authorization).toBeUndefined()
    expect(route.request().postDataJSON()).toEqual(credentials)
    await route.fulfill({ status: 200, json: { ...session, token_type: 'bearer' } })
  })
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Sesión iniciada correctamente')
  expect(await stored_session(page)).toEqual(session)
  await expect(page).toHaveURL('/home')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  expect(await stored_session(page)).toEqual(session)
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL('/login')
  expect(await stored_session(page)).toBeNull()
})

test('muestra el error del backend en 401 y permite reintentar', async ({ page }) => {
  await page.route('**/api/auth/login', (route) => route.fulfill({
    status: 401, json: { detail: 'Email o contraseña incorrectos' },
  }))
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Credenciales inválidas')
  await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos')
  expect(await stored_session(page)).toBeNull()
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('button', { name: 'Iniciar sesión', exact: true })).toBeEnabled()
  await page.route('**/api/auth/login', (route) => route.fulfill({ json: session }))
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page).toHaveURL('/home')
})

test('bloquea el formulario mientras espera al servidor', async ({ page }) => {
  let respond
  const response = new Promise((resolve) => { respond = resolve })
  await page.route('**/api/auth/login', async (route) => {
    await response
    await route.fulfill({ json: session })
  })
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Iniciando sesión…' })).toBeDisabled()
  await expect(page.getByLabel('Email')).toBeDisabled()
  await expect(page.getByLabel('Contraseña', { exact: true })).toBeDisabled()
  respond()
  await expect(page).toHaveURL('/home')
})

test('muestra un error de conexión sin guardar sesión', async ({ page }) => {
  await page.route('**/api/auth/login', (route) => route.abort())
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('No se pudo conectar')
  expect(await stored_session(page)).toBeNull()
})

test('no redirige si no puede persistir la sesión', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => { throw new Error('Almacenamiento bloqueado') }
  })
  await page.route('**/api/auth/login', (route) => route.fulfill({ json: session }))
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('No se pudo guardar la sesión')
  await expect(page).toHaveURL('/login')
})

test('rechaza una respuesta de éxito incompleta', async ({ page }) => {
  await page.route('**/api/auth/login', (route) => route.fulfill({ json: { access_token: 'incompleto' } }))
  await fill_login(page)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  expect(await stored_session(page)).toBeNull()
  await expect(page).toHaveURL('/login')
})

test('home requiere una sesión válida', async ({ page }) => {
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
  await page.evaluate(() => localStorage.setItem('futbot.session', '{invalid'))
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
})


test('rechaza en home un token vencido o inventado y borra la sesión', async ({ page }) => {
  await page.route('**/api/auth/me', async (route) => {
    expect(route.request().headers().authorization).toBe('Bearer token-inventado')
    await route.fulfill({ status: 401, json: { detail: 'Sesión inválida o vencida' } })
  })
  await page.goto('/login')
  await page.evaluate(() => localStorage.setItem('futbot.session', JSON.stringify({
    expires_at: Math.floor(Date.now() / 1000) + 300, access_token: 'token-inventado', refresh_token: 'refresh-inventado', club_id: 'club-inventado',
  })))
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
  expect(await stored_session(page)).toBeNull()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toHaveCount(0)
})

test('espera validación del servidor antes de mostrar el menú', async ({ page }) => {
  let respond
  const response = new Promise((resolve) => { respond = resolve })
  await page.route('**/api/auth/me', async (route) => {
    await response
    await route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } })
  })
  await page.goto('/login')
  await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), session)
  await page.goto('/home')
  await expect(page.getByRole('status')).toContainText('Verificando sesión')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toHaveCount(0)
  respond()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
})

test('un fallo de conexión conserva la sesión y permite reintentar', async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.abort())
  await page.goto('/login')
  await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), session)
  await page.goto('/home')
  await expect(page.getByRole('alert')).toContainText('No se pudo verificar')
  expect(await stored_session(page)).toEqual(session)
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user_id: 'test-user', club_id: session.club_id } }))
  await page.getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
})

test('conserva la sesión persistente y verifica el usuario al recargar', async ({ page }) => {
  await page.goto('/login')
  await page.evaluate((value) => localStorage.setItem('futbot.session', JSON.stringify(value)), session)
  await page.goto('/login')
  await expect(page).toHaveURL('/home')
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  expect(await stored_session(page)).toEqual(session)
})

test('permite mostrar y ocultar la contraseña sin enviar el formulario', async ({ page }) => {
  await fill_login(page)
  await page.getByRole('button', { name: 'Mostrar contraseña', exact: true }).click()
  await expect(page.getByLabel('Contraseña', { exact: true })).toHaveAttribute('type', 'text')
  await expect(page.getByLabel('Contraseña', { exact: true })).toHaveValue(credentials.password)
  await page.getByRole('button', { name: 'Ocultar contraseña', exact: true }).click()
  await expect(page.getByLabel('Contraseña', { exact: true })).toHaveAttribute('type', 'password')
  expect(await stored_session(page)).toBeNull()
})

test('sin Recordarme conserva la sesión solo en la pestaña y la borra al salir', async ({ page }) => {
  await page.route('**/api/auth/login', (route) => route.fulfill({ json: session }))
  await fill_login(page)
  await page.getByLabel('Recordarme').uncheck()
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  expect(await stored_session(page)).toBeNull()
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('futbot.session')))).toEqual(session)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Menú principal' })).toBeVisible()
  expect(await stored_session(page)).toBeNull()
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => sessionStorage.getItem('futbot.session'))).toBeNull()
})
