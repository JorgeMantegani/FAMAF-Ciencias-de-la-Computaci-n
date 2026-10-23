import { expect, test } from '@playwright/test'

const session = {
  expires_at: Math.floor(Date.now() / 1000) + 300,
  access_token: 'token-simulado',
  refresh_token: 'refresh-simulado',
  club_id: 'b7118fc1-a066-4fa4-b197-92e0ed6758fd',
}

const ROOM_ID = '11111111-1111-4111-8111-111111111111'
const OTHER_ROOM_ID = '22222222-2222-4222-8222-222222222222'
const ROOM_CODE = 'ABC123'

const players = [
  { id: 'player-ana', name: 'Ana' },
  { id: 'player-beto', name: 'Beto' },
  { id: 'player-carla', name: 'Carla' },
  { id: 'player-dani', name: 'Dani' },
  { id: 'player-eva', name: 'Eva' },
  { id: 'player-fito', name: 'Fito' },
  { id: 'player-gus', name: 'Gus' },
]

const behaviors = [
  { id: 'behavior-front', name: 'Delantero' },
  { id: 'behavior-defense', name: 'Defensa' },
  { id: 'behavior-keeper', name: 'Arquero' },
]

const starters = ['Ana', 'Beto', 'Carla']
const substitutes = ['Dani', 'Eva', 'Fito']

const team = {
  Ana: 'Delantero',
  Beto: 'Defensa',
  Carla: 'Arquero',
  Dani: 'Delantero',
  Eva: 'Defensa',
  Fito: 'Arquero',
}

const player_id = (name) =>
  players.find((player) => player.name === name).id

const behavior_id = (label) =>
  behaviors.find((behavior) => behavior.name === label).id

const selection_of = (names) =>
  names.map((name) => ({
    playerId: player_id(name),
    behaviorId: behavior_id(team[name]),
  }))

const expected_body = {
  code: ROOM_CODE,
  starters: selection_of(starters),
  substitutes: selection_of(substitutes),
}

const joined = {
  roomId: ROOM_ID,
  status: 'readyToStart',
  awayClub: session.club_id,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/logout', (route) =>
    route.fulfill({ status: 204 }),
  )

  await page.route('**/api/auth/me', async (route) => {
    expect(route.request().headers().authorization).toBe(
      `Bearer ${session.access_token}`,
    )

    await route.fulfill({
      json: {
        user_id: 'test-user',
        club_id: session.club_id,
      },
    })
  })

  await page.route('**/api/players', async (route) => {
    expect(route.request().headers().authorization).toBe(
      `Bearer ${session.access_token}`,
    )

    await route.fulfill({
      json: players,
    })
  })

  // El flujo nuevo usa list_behaviors() -> /api/behaviors.
  await page.route('**/api/behaviors', async (route) => {
    expect(route.request().headers().authorization).toBe(
      `Bearer ${session.access_token}`,
    )

    await route.fulfill({
      json: behaviors,
    })
  })
})

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

async function stored_session(page) {
  return page.evaluate(() =>
    JSON.parse(localStorage.getItem('futbot.session')),
  )
}

async function seed_session(page) {
  await page.goto('/login')

  await page.evaluate(
    (value) =>
      localStorage.setItem(
        'futbot.session',
        JSON.stringify(value),
      ),
    session,
  )
}

async function open_home(page) {
  await seed_session(page)

  await page.goto('/home')

  await expect(
    page.getByRole('heading', {
      name: 'Menú principal',
    }),
  ).toBeVisible()
}

async function open_join_modal(page) {
  await page
    .getByRole('button', {
      name: 'Unirse a un amistoso',
      exact: true,
    })
    .click()

  await expect(
    page
      .getByRole('dialog')
      .getByRole('heading', {
        name: 'Unirse a un amistoso',
      }),
  ).toBeVisible()
}

async function fill_modal(page, room_id, code) {
  await page.getByLabel('ID de la sala').fill(room_id)
  await page.getByLabel('Código de la sala').fill(code)

  await page
    .getByRole('button', {
      name: 'Continuar',
      exact: true,
    })
    .click()
}

async function open_join_page(page) {
  await open_home(page)
  await open_join_modal(page)
  await fill_modal(page, ROOM_ID, ROOM_CODE)

  await expect(page).toHaveURL('/friendly/join')

  await expect(
    page.getByRole('heading', {
      name: 'Unirse a amistoso',
      exact: true,
    }),
  ).toBeVisible()
}

/*
 * SquadSelector renderiza 6 .slot-card:
 *
 *   Titular 1
 *   Titular 2
 *   Titular 3
 *
 *   Suplente 1
 *   Suplente 2
 *   Suplente 3
 *
 * Cada slot tiene dos combobox:
 *
 *   0 = jugador
 *   1 = comportamiento
 */

function slot(page, group, index) {
  return page
    .locator('.slot-card')
    .filter({
      hasText: `${group} ${index + 1}`,
    })
}

function player_select(page, group, index) {
  return slot(page, group, index)
    .getByRole('combobox')
    .nth(0)
}

function behavior_select(page, group, index) {
  return slot(page, group, index)
    .getByRole('combobox')
    .nth(1)
}

async function choose_player(page, group, index, name) {
  await player_select(page, group, index).selectOption({
    label: name,
  })
}

async function choose_behavior(page, group, index, label) {
  await behavior_select(page, group, index).selectOption({
    label,
  })
}

async function fill_slots(page, names, group) {
  for (let index = 0; index < names.length; index += 1) {
    await choose_player(
      page,
      group,
      index,
      names[index],
    )

    await choose_behavior(
      page,
      group,
      index,
      team[names[index]],
    )
  }
}

async function fill_team(page) {
  await fill_slots(page, starters, 'Titular')
  await fill_slots(page, substitutes, 'Suplente')
}

const confirm_button = (page) =>
  page.getByRole('button', {
    name: /^(Confirmar y unirse|Uniéndote…)$/,
  })

async function mock_join(page, status, json) {
  const requests = []

  await page.route(
    '**/api/friendly/rooms/*/join',
    async (route) => {
      const request = route.request()

      requests.push({
        method: request.method(),
        url: request.url(),
        headers: request.headers(),
        body: request.postDataJSON(),
      })

      await route.fulfill({
        status,
        json,
      })
    },
  )

  return requests
}

// -----------------------------------------------------------------------------
// Menú / modal
// -----------------------------------------------------------------------------

test('el menú ofrece unirse a un amistoso y abre la ventana de ID y código', async ({
  page,
}) => {
  await open_home(page)
  await open_join_modal(page)

  await expect(
    page.getByLabel('ID de la sala'),
  ).toBeVisible()

  await expect(
    page.getByLabel('Código de la sala'),
  ).toBeVisible()
})

test('valida el ID y el código antes de continuar', async ({
  page,
}) => {
  await open_home(page)
  await open_join_modal(page)

  const dialog = page.getByRole('dialog')

  await page
    .getByRole('button', {
      name: 'Continuar',
      exact: true,
    })
    .click()

  await expect(
    dialog.getByRole('alert'),
  ).toContainText(
    'El ID de la sala no tiene un formato válido',
  )

  await page
    .getByLabel('ID de la sala')
    .fill(ROOM_ID)

  await page
    .getByRole('button', {
      name: 'Continuar',
      exact: true,
    })
    .click()

  await expect(
    dialog.getByRole('alert'),
  ).toContainText(
    'El código debe tener 6 caracteres',
  )

  await page
    .getByLabel('Código de la sala')
    .fill('AB1')

  await page
    .getByRole('button', {
      name: 'Continuar',
      exact: true,
    })
    .click()

  await expect(
    dialog.getByRole('alert'),
  ).toContainText(
    'El código debe tener 6 caracteres',
  )

  await expect(page).toHaveURL('/home')
})

test('el código se escribe en mayúsculas', async ({
  page,
}) => {
  await open_home(page)
  await open_join_modal(page)

  await page
    .getByLabel('Código de la sala')
    .fill('abc123')

  await expect(
    page.getByLabel('Código de la sala'),
  ).toHaveValue('ABC123')
})

test('Cancelar y Escape cierran la ventana sin navegar y limpian los campos', async ({
  page,
}) => {
  await open_home(page)
  await open_join_modal(page)

  await page
    .getByLabel('ID de la sala')
    .fill(ROOM_ID)

  await page
    .getByRole('button', {
      name: 'Cancelar',
      exact: true,
    })
    .click()

  await expect(
    page.getByRole('dialog'),
  ).toBeHidden()

  await open_join_modal(page)

  await expect(
    page.getByLabel('ID de la sala'),
  ).toHaveValue('')

  await page.keyboard.press('Escape')

  await expect(
    page.getByRole('dialog'),
  ).toBeHidden()

  await expect(page).toHaveURL('/home')
})

test('con ID y código válidos pasa a la selección de jugadores', async ({
  page,
}) => {
  await open_join_page(page)

  await expect(
    page.getByText(`Sala: ${ROOM_ID}`),
  ).toBeVisible()
})

// -----------------------------------------------------------------------------
// Acceso
// -----------------------------------------------------------------------------

test('sin sesión, la pantalla de selección lleva al login', async ({
  page,
}) => {
  await page.goto('/friendly/join')

  await expect(page).toHaveURL('/login')
})

test('con sesión pero sin sala elegida, vuelve al menú', async ({
  page,
}) => {
  await seed_session(page)

  await page.goto('/friendly/join')

  await expect(page).toHaveURL('/home')

  await expect(
    page.getByRole('heading', {
      name: 'Menú principal',
    }),
  ).toBeVisible()
})

// -----------------------------------------------------------------------------
// Nueva selección de jugadores / comportamientos
// -----------------------------------------------------------------------------

test('muestra los 3 slots de titulares y los 3 de suplentes', async ({
  page,
}) => {
  await open_join_page(page)

  await expect(
    page.getByRole('heading', {
      name: 'Unirse a amistoso',
      exact: true,
    }),
  ).toBeVisible()

  await expect(
    page.getByText(
      'Titulares (3 requeridos)',
      { exact: true },
    ),
  ).toBeVisible()

  await expect(
    page.getByText(
      'Suplentes (3 requeridos)',
      { exact: true },
    ),
  ).toBeVisible()

  await expect(
    page.locator('.slot-card'),
  ).toHaveCount(6)

  for (const label of [
    'Titular',
    'Suplente',
  ]) {
    for (let index = 0; index < 3; index += 1) {
      await expect(
        slot(page, label, index),
      ).toBeVisible()

      await expect(
        slot(page, label, index)
          .getByRole('combobox'),
      ).toHaveCount(2)
    }
  }

  await expect(
    confirm_button(page),
  ).toBeDisabled()
})

test('cada slot permite seleccionar un jugador y un comportamiento', async ({
  page,
}) => {
  await open_join_page(page)

  await choose_player(
    page,
    'Titular',
    0,
    'Ana',
  )

  await choose_behavior(
    page,
    'Titular',
    0,
    'Defensa',
  )

  await expect(
    player_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('player-ana')

  await expect(
    behavior_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('behavior-defense')

  await choose_player(
    page,
    'Suplente',
    0,
    'Dani',
  )

  await choose_behavior(
    page,
    'Suplente',
    0,
    'Delantero',
  )

  await expect(
    player_select(
      page,
      'Suplente',
      0,
    ),
  ).toHaveValue('player-dani')

  await expect(
    behavior_select(
      page,
      'Suplente',
      0,
    ),
  ).toHaveValue('behavior-front')
})

test('un jugador seleccionado queda deshabilitado en los demás slots', async ({
  page,
}) => {
  await open_join_page(page)

  await choose_player(
    page,
    'Titular',
    0,
    'Ana',
  )

  const other_player_select =
    player_select(
      page,
      'Titular',
      1,
    )

  const substitute_player_select =
    player_select(
      page,
      'Suplente',
      0,
    )

  await expect(
    other_player_select.locator(
      'option[value="player-ana"]',
    ),
  ).toBeDisabled()

  await expect(
    substitute_player_select.locator(
      'option[value="player-ana"]',
    ),
  ).toBeDisabled()

  await expect(
    player_select(
      page,
      'Titular',
      0,
    ).locator(
      'option[value="player-ana"]',
    ),
  ).not.toBeDisabled()
})

test('los jugadores no desaparecen de los selects al elegir otro jugador', async ({
  page,
}) => {
  await open_join_page(page)

  await choose_player(
    page,
    'Titular',
    0,
    'Ana',
  )

  await choose_player(
    page,
    'Titular',
    1,
    'Beto',
  )

  const select =
    player_select(
      page,
      'Suplente',
      0,
    )

  await expect(
    select.locator(
      'option[value="player-ana"]',
    ),
  ).toHaveCount(1)

  await expect(
    select.locator(
      'option[value="player-beto"]',
    ),
  ).toHaveCount(1)

  await expect(
    select.locator(
      'option[value="player-ana"]',
    ),
  ).toBeDisabled()

  await expect(
    select.locator(
      'option[value="player-beto"]',
    ),
  ).toBeDisabled()

  await expect(
    select.locator(
      'option[value="player-carla"]',
    ),
  ).toBeEnabled()
})

test('permite cambiar un jugador de un slot sin perder los otros', async ({
  page,
}) => {
  await open_join_page(page)

  await choose_player(
    page,
    'Titular',
    0,
    'Ana',
  )

  await choose_player(
    page,
    'Titular',
    1,
    'Beto',
  )

  await choose_player(
    page,
    'Suplente',
    0,
    'Dani',
  )

  await choose_player(
    page,
    'Titular',
    0,
    'Carla',
  )

  await expect(
    player_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('player-carla')

  await expect(
    player_select(
      page,
      'Titular',
      1,
    ),
  ).toHaveValue('player-beto')

  await expect(
    player_select(
      page,
      'Suplente',
      0,
    ),
  ).toHaveValue('player-dani')

  await expect(
    player_select(
      page,
      'Suplente',
      1,
    ).locator(
      'option[value="player-ana"]',
    ),
  ).toBeEnabled()
})

test('los seis slots empiezan sin jugador ni comportamiento', async ({
  page,
}) => {
  await open_join_page(page)

  for (const label of [
    'Titular',
    'Suplente',
  ]) {
    for (let index = 0; index < 3; index += 1) {
      await expect(
        player_select(
          page,
          label,
          index,
        ),
      ).toHaveValue('')

      await expect(
        behavior_select(
          page,
          label,
          index,
        ),
      ).toHaveValue('')
    }
  }
})

test('no permite confirmar hasta completar los 6 jugadores', async ({
  page,
}) => {
  await open_join_page(page)

  await choose_player(
    page,
    'Titular',
    0,
    'Ana',
  )

  await choose_behavior(
    page,
    'Titular',
    0,
    'Delantero',
  )

  await choose_player(
    page,
    'Titular',
    1,
    'Beto',
  )

  await choose_behavior(
    page,
    'Titular',
    1,
    'Defensa',
  )

  await choose_player(
    page,
    'Titular',
    2,
    'Carla',
  )

  await choose_behavior(
    page,
    'Titular',
    2,
    'Arquero',
  )

  await choose_player(
    page,
    'Suplente',
    0,
    'Dani',
  )

  await choose_behavior(
    page,
    'Suplente',
    0,
    'Delantero',
  )

  await choose_player(
    page,
    'Suplente',
    1,
    'Eva',
  )

  await choose_behavior(
    page,
    'Suplente',
    1,
    'Defensa',
  )

  await expect(
    confirm_button(page),
  ).toBeDisabled()
})

test('no permite confirmar si falta un comportamiento', async ({
  page,
}) => {
  await open_join_page(page)

  for (
    let index = 0;
    index < starters.length;
    index += 1
  ) {
    const name = starters[index]

    await choose_player(
      page,
      'Titular',
      index,
      name,
    )

    await choose_behavior(
      page,
      'Titular',
      index,
      team[name],
    )
  }

  for (
    let index = 0;
    index < substitutes.length;
    index += 1
  ) {
    await choose_player(
      page,
      'Suplente',
      index,
      substitutes[index],
    )
  }

  await choose_behavior(
    page,
    'Suplente',
    0,
    team.Dani,
  )

  await choose_behavior(
    page,
    'Suplente',
    1,
    team.Eva,
  )

  await expect(
    confirm_button(page),
  ).toBeDisabled()

  await choose_behavior(
    page,
    'Suplente',
    2,
    team.Fito,
  )

  await expect(
    confirm_button(page),
  ).toBeEnabled()
})

test('con el equipo completo se puede confirmar', async ({
  page,
}) => {
  await open_join_page(page)
  await fill_team(page)

  await expect(
    confirm_button(page),
  ).toBeEnabled()
})

test('con menos de 6 jugadores creados avisa y no deja confirmar', async ({
  page,
}) => {
  await page.route(
    '**/api/players',
    (route) =>
      route.fulfill({
        json: players.slice(0, 3),
      }),
  )

  await open_join_page(page)

  await expect(
    page.getByText(
      'Necesitás al menos 6 jugadores distintos para completar titulares y suplentes.',
    ),
  ).toBeVisible()

  await expect(
    page.locator('.slot-card'),
  ).toHaveCount(6)

  await expect(
    confirm_button(page),
  ).toBeDisabled()
})

test('un error al cargar los jugadores permite reintentar', async ({
  page,
}) => {
  let failing = true

  await page.route(
    '**/api/players',
    (route) =>
      failing
        ? route.fulfill({
            status: 500,
            json: {
              detail: 'Servidor caído',
              error_code:
                'INTERNAL_SERVER_ERROR',
            },
          })
        : route.fulfill({
            json: players,
          }),
  )

  await open_join_page(page)

  await expect(
    page.getByRole('alert'),
  ).toContainText('Servidor caído')

  failing = false

  await page
    .getByRole('button', {
      name: 'Reintentar',
      exact: true,
    })
    .click()

  await expect(
    page.getByText(
      'Titulares (3 requeridos)',
    ),
  ).toBeVisible()

  await expect(
    page.locator('.slot-card'),
  ).toHaveCount(6)
})

test('una sesión vencida al cargar los jugadores lleva al login', async ({
  page,
}) => {
  await page.route(
    '**/api/players',
    (route) =>
      route.fulfill({
        status: 401,
        json: {
          detail: 'Sesión vencida',
          error_code: 'UNAUTHORIZED',
        },
      }),
  )

  await open_join_page(page).catch(() => {})

  await expect(page).toHaveURL('/login')

  expect(
    await stored_session(page),
  ).toBeNull()
})

// -----------------------------------------------------------------------------
// Confirmar
// -----------------------------------------------------------------------------

test('confirmar envía el POST con token, código y los 6 slots', async ({
  page,
}) => {
  const requests = await mock_join(
    page,
    200,
    joined,
  )

  await open_join_page(page)
  await fill_team(page)

  await expect(
    confirm_button(page),
  ).toBeEnabled()

  await confirm_button(page).click()

  await expect(page).toHaveURL(
    `/amistosos/${ROOM_ID}/sala`,
  )

  expect(requests).toHaveLength(1)

  expect(
    requests[0].method,
  ).toBe('POST')

  expect(
    requests[0].url,
  ).toMatch(
    new RegExp(
      `/api/friendly/rooms/${ROOM_ID}/join$`,
    ),
  )

  expect(
    requests[0].headers.authorization,
  ).toBe(
    `Bearer ${session.access_token}`,
  )

  expect(
    requests[0].body,
  ).toEqual(expected_body)
})

test('bloquea Confirmar mientras espera al servidor', async ({
  page,
}) => {
  let respond

  const response = new Promise(
    (resolve) => {
      respond = resolve
    },
  )

  await page.route(
    '**/api/friendly/rooms/*/join',
    async (route) => {
      await response

      await route.fulfill({
        json: joined,
      })
    },
  )

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  await expect(
    page.getByRole('button', {
      name: 'Uniéndote…',
    }),
  ).toBeDisabled()

  respond()

  await expect(page).toHaveURL(
    `/amistosos/${ROOM_ID}/sala`,
  )
})

test('código de sala inválido (404) permite ingresar otro sin perder la selección', async ({
  page,
}) => {
  const requests = []

  await page.route(
    '**/api/friendly/rooms/*/join',
    async (route) => {
      const request = route.request()

      requests.push({
        url: request.url(),
        body: request.postDataJSON(),
      })

      if (
        request.url().includes(ROOM_ID)
      ) {
        await route.fulfill({
          status: 404,
          json: {
            detail:
              'Sala no encontrada o codigo incorrecto',
            error_code:
              'ROOM_NOT_FOUND',
          },
        })
      } else {
        await route.fulfill({
          json: {
            ...joined,
            roomId: OTHER_ROOM_ID,
          },
        })
      }
    },
  )

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  const notice = page.getByRole('dialog')

  await expect(
    notice.getByRole('heading', {
      name: 'No se encontró la sala',
    }),
  ).toBeVisible()

  await expect(
    notice.getByRole('alert'),
  ).toContainText(
    'La sala no existe o el ID no es válido.',
  )

  await notice
    .getByRole('button', {
      name: 'Ingresar otra sala',
    })
    .click()

  await expect(
    page
      .getByRole('dialog')
      .getByRole('heading', {
        name: 'Unirse a un amistoso',
      }),
  ).toBeVisible()

  await fill_modal(
    page,
    OTHER_ROOM_ID,
    'ZZZ999',
  )

  await expect(
    page.getByText(
      `Sala: ${OTHER_ROOM_ID}`,
    ),
  ).toBeVisible()

  // La selección se conserva al cambiar de sala.
  await expect(
    player_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('player-ana')

  await expect(
    behavior_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('behavior-front')

  await expect(
    player_select(
      page,
      'Suplente',
      2,
    ),
  ).toHaveValue('player-fito')

  await expect(
    confirm_button(page),
  ).toBeEnabled()

  await confirm_button(page).click()

  await expect(page).toHaveURL(
    `/amistosos/${OTHER_ROOM_ID}/sala`,
  )

  expect(requests).toHaveLength(2)

  expect(
    requests[1].url,
  ).toMatch(
    new RegExp(
      `/${OTHER_ROOM_ID}/join$`,
    ),
  )

  expect(
    requests[1].body.code,
  ).toBe('ZZZ999')

  expect(
    requests[1].body.starters,
  ).toEqual(
    selection_of(starters),
  )

  expect(
    requests[1].body.substitutes,
  ).toEqual(
    selection_of(substitutes),
  )
})

test('sala completa (400) informa que no puede unirse', async ({
  page,
}) => {
  await mock_join(page, 400, {
    detail:
      'La sala esta completa o fue iniciada.',
    error_code: 'BAD_REQUEST',
  })

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  const notice = page.getByRole('dialog')

  await expect(
    notice.getByRole('heading', {
      name: 'Sala no disponible',
    }),
  ).toBeVisible()

  await expect(
    notice.getByRole('alert'),
  ).toContainText(
    'La sala esta completa o fue iniciada.',
  )

  await expect(
    notice.getByRole('button', {
      name: 'Volver a seleccionar',
    }),
  ).toHaveCount(0)

  await notice
    .getByRole('button', {
      name: 'Volver al menú',
    })
    .click()

  await expect(page).toHaveURL('/home')
})

test('selección inválida (400) permite volver a seleccionar desde cero', async ({
  page,
}) => {
  const detail =
    'Al menos un jugador seleccionado no pertenece a tu club o no esta disponible.'

  await mock_join(page, 400, {
    detail,
    error_code: 'INVALID_SQUAD',
  })

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  const notice = page.getByRole('dialog')

  await expect(
    notice.getByRole('heading', {
      name: 'Selección no válida',
    }),
  ).toBeVisible()

  await expect(
    notice.getByRole('alert'),
  ).toContainText(detail)

  await notice
    .getByRole('button', {
      name: 'Volver a seleccionar',
    })
    .click()

  await expect(
    page.getByText(
      'Titulares (3 requeridos)',
    ),
  ).toBeVisible()

  for (const label of [
    'Titular',
    'Suplente',
  ]) {
    for (let index = 0; index < 3; index += 1) {
      await expect(
        player_select(
          page,
          label,
          index,
        ),
      ).toHaveValue('')

      await expect(
        behavior_select(
          page,
          label,
          index,
        ),
      ).toHaveValue('')
    }
  }

  await expect(
    confirm_button(page),
  ).toBeDisabled()
})

test('datos no válidos (422) avisan y conservan la selección', async ({
  page,
}) => {
  await mock_join(page, 422, {
    detail: [
      {
        loc: ['body'],
        msg: 'Field required',
        type: 'missing',
      },
    ],
    error_code: 'VALIDATION_ERROR',
  })

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  const notice = page.getByRole('dialog')

  await expect(
    notice.getByRole('heading', {
      name: 'Datos no válidos',
    }),
  ).toBeVisible()

  await notice
    .getByRole('button', {
      name: 'Cerrar',
    })
    .click()

  await expect(
    page.getByRole('dialog'),
  ).toBeHidden()

  await expect(
    player_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('player-ana')

  await expect(
    behavior_select(
      page,
      'Titular',
      0,
    ),
  ).toHaveValue('behavior-front')

  await expect(
    player_select(
      page,
      'Suplente',
      2,
    ),
  ).toHaveValue('player-fito')
})

test('un error de conexión avisa y permite reintentar', async ({
  page,
}) => {
  await page.route(
    '**/api/friendly/rooms/*/join',
    (route) => route.abort(),
  )

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  const notice = page.getByRole('dialog')

  await expect(
    notice.getByRole('heading', {
      name: 'No se pudo unir al amistoso',
    }),
  ).toBeVisible()

  await expect(
    notice.getByRole('alert'),
  ).toContainText(
    'No se pudo conectar con el servidor',
  )

  await notice
    .getByRole('button', {
      name: 'Cerrar',
    })
    .click()

  await expect(
    confirm_button(page),
  ).toBeEnabled()
})

test('Escape no cierra los avisos: hay que elegir una de sus acciones', async ({
  page,
}) => {
  await page.route(
    '**/api/friendly/rooms/*/join',
    (route) => route.abort(),
  )

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  await expect(
    page
      .getByRole('dialog')
      .getByRole('heading', {
        name: 'No se pudo unir al amistoso',
      }),
  ).toBeVisible()

  await page.keyboard.press('Escape')

  await expect(
    page
      .getByRole('dialog')
      .getByRole('heading', {
        name: 'No se pudo unir al amistoso',
      }),
  ).toBeVisible()
})

test('un 401 al confirmar borra la sesión y lleva al login', async ({
  page,
}) => {
  await mock_join(page, 401, {
    detail: 'Sesión inválida o vencida',
    error_code: 'UNAUTHORIZED',
  })

  await open_join_page(page)
  await fill_team(page)

  await confirm_button(page).click()

  await expect(page).toHaveURL('/login')

  expect(
    await stored_session(page),
  ).toBeNull()
})