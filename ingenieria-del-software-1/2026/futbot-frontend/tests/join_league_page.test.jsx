import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import JoinLeaguePage from '../src/pages/join_league_page'
import { list_behaviors, list_players } from '../src/api/client'
import { get_league, join_league } from '../src/api/leagues'
import { clear_session, save_session } from '../src/auth/session'
import { useLeaguesSocket } from '../src/hooks/use_leagues_socket'

vi.mock('../src/hooks/use_leagues_socket', () => ({ useLeaguesSocket: vi.fn() }))

vi.mock('../src/api/client', () => ({
  request: vi.fn(),
  list_players: vi.fn(),
  list_behaviors: vi.fn(),
}))

vi.mock('../src/api/leagues', async (import_original) => ({
  ...(await import_original()),
  get_league: vi.fn(),
  join_league: vi.fn(),
}))

const LEAGUE_ID = '11111111-1111-4111-8111-111111111111'

const players = ['Ana', 'Beto', 'Carla', 'Dani', 'Eva', 'Fito'].map((name, index) => ({
  id: `player-${index + 1}`,
  name,
}))

const behaviors = [
  { id: 'behavior-1', name: 'Delantero' },
  { id: 'behavior-2', name: 'Defensa' },
]

const league = (overrides = {}) => ({
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

const chosen = (index) => ({
  playerId: `player-${index + 1}`,
  behaviorId: behaviors[index % 2].id,
})

const api_error = (status, error_code) =>
  Object.assign(new Error('error del backend'), { status, error_code })

const listed_league = (participants_count, overrides = {}) => ({
  id: LEAGUE_ID,
  name: 'Liga del Barrio',
  participants_count,
  started: false,
  ...overrides,
})

const receive_list = (...listed) =>
  act(() => useLeaguesSocket.mock.lastCall[1](listed))

beforeEach(() => {
  vi.resetAllMocks()
  save_session({
    access_token: 'token',
    refresh_token: 'refresh',
    club_id: 'club',
    expires_at: Date.now() / 1000 + 3600,
  })
  get_league.mockResolvedValue(league())
  list_players.mockResolvedValue(players)
  list_behaviors.mockResolvedValue(behaviors)
})

afterEach(() => {
  clear_session()
})

function render_page() {
  render(
    <MemoryRouter initialEntries={[`/ligas/${LEAGUE_ID}/unirse`]}>
      <Routes>
        <Route path="/ligas/:league_id/unirse" element={<JoinLeaguePage />} />
        <Route path="/league/:league_id/waiting" element={<LobbyStub />} />
        <Route path="/home" element={<p>Menú principal</p>} />
        <Route path="/login" element={<p>Pantalla de login</p>} />
      </Routes>
    </MemoryRouter>
  )
}

function LobbyStub() {
  const { league_id } = useParams()
  return <p>Lobby de {league_id}</p>
}

const lobby_text = `Lobby de ${LEAGUE_ID}`

async function mount() {
  render_page()
  await screen.findByRole('heading', { name: 'Liga del Barrio' })
  return userEvent.setup()
}

async function fill_squad(user, { skip_last_behavior = false } = {}) {
  const selects = screen.getAllByRole('combobox')

  for (let index = 0; index < 6; index += 1) {
    await user.selectOptions(selects[index * 2], chosen(index).playerId)
    if (skip_last_behavior && index === 5) continue
    await user.selectOptions(selects[index * 2 + 1], chosen(index).behaviorId)
  }
}

const confirm_button = () => screen.getByRole('button', { name: 'Confirmar inscripción' })

describe('loading', () => {
  it('shows the basic league information', async () => {
    await mount()

    const facts = screen.getByRole('region', { name: 'Liga del Barrio' })
    expect(within(facts).getByText('Pública')).toBeInTheDocument()
    expect(within(facts).getByText('Esperando clubes')).toBeInTheDocument()
    expect(within(facts).getByText('3 de 8')).toBeInTheDocument()
    expect(within(facts).getByText('3 clubes')).toBeInTheDocument()
    expect(within(facts).getByText('10 minutos')).toBeInTheDocument()
    expect(get_league).toHaveBeenCalledWith(LEAGUE_ID, expect.anything())
  })

  it('offers to go back without retrying when the league does not exist', async () => {
    get_league.mockRejectedValue(api_error(404, 'LEAGUE_NOT_FOUND'))
    render(
      <MemoryRouter initialEntries={[`/ligas/${LEAGUE_ID}/unirse`]}>
        <Routes>
          <Route path="/ligas/:league_id/unirse" element={<JoinLeaguePage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La liga no existe o el ID no es válido.'
    )
    expect(screen.getByRole('button', { name: 'Volver al menú' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  it('lets the user retry after a failed load', async () => {
    get_league.mockRejectedValueOnce(api_error(500, 'INTERNAL_SERVER_ERROR'))
    render(
      <MemoryRouter initialEntries={[`/ligas/${LEAGUE_ID}/unirse`]}>
        <Routes>
          <Route path="/ligas/:league_id/unirse" element={<JoinLeaguePage />} />
        </Routes>
      </MemoryRouter>
    )
    const user = userEvent.setup()

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar la liga.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('heading', { name: 'Liga del Barrio' })).toBeInTheDocument()
    expect(get_league).toHaveBeenCalledTimes(2)
  })

  it('sends the user to the login without a session', async () => {
    clear_session()
    render(
      <MemoryRouter initialEntries={[`/ligas/${LEAGUE_ID}/unirse`]}>
        <Routes>
          <Route path="/ligas/:league_id/unirse" element={<JoinLeaguePage />} />
          <Route path="/login" element={<p>Pantalla de login</p>} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('Pantalla de login')).toBeInTheDocument()
    expect(get_league).not.toHaveBeenCalled()
  })
})

describe('squad selection', () => {
  it('shows three starter and three substitute slots', async () => {
    await mount()

    expect(screen.getByText('Titulares (3 requeridos)')).toBeInTheDocument()
    expect(screen.getByText('Suplentes (3 requeridos)')).toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(12)
  })

  it('keeps confirm disabled until every player has a behavior', async () => {
    const user = await mount()
    expect(confirm_button()).toBeDisabled()

    await fill_squad(user, { skip_last_behavior: true })
    expect(confirm_button()).toBeDisabled()

    await user.selectOptions(screen.getAllByRole('combobox')[11], chosen(5).behaviorId)
    expect(confirm_button()).toBeEnabled()
  })

  it('warns when the club has fewer than six players', async () => {
    list_players.mockResolvedValue(players.slice(0, 3))
    await mount()

    expect(
      screen.getByText(/Tenés 3 jugadores. Necesitás al menos 6 jugadores distintos/)
    ).toBeInTheDocument()
    expect(confirm_button()).toBeDisabled()
  })
})

describe('leagues that cannot be joined', () => {
  it.each([
    ['already started', { status: 'inProgress' }, 'La liga ya no admite inscripciones.'],
    ['full', { enrolledClubs: 8 }, 'La liga está completa: ya no es posible unirse.'],
  ])('a %s league shows the reason and no squad selector', async (_, overrides, message) => {
    get_league.mockResolvedValue(league(overrides))
    await mount()

    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
    expect(screen.getByRole('button', { name: 'Volver al menú' })).toBeInTheDocument()
  })

  it('goes straight to the lobby when the club is already enrolled', async () => {
    get_league.mockResolvedValue(league({ isEnrolled: true }))
    render_page()

    expect(await screen.findByText(lobby_text)).toBeInTheDocument()
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
  })
})

describe('private leagues', () => {
  beforeEach(() => {
    get_league.mockResolvedValue(league({ isPrivate: true }))
  })

  it('a public league does not ask for a password', async () => {
    get_league.mockResolvedValue(league())
    await mount()

    expect(screen.queryByLabelText('Contraseña de la liga')).not.toBeInTheDocument()
  })

  it('asks for the password and keeps confirm disabled until it is filled', async () => {
    const user = await mount()

    expect(screen.getByLabelText('Contraseña de la liga')).toHaveAccessibleDescription(
      'Es una liga privada: pedile la contraseña a quien la creó.'
    )
    expect(screen.queryAllByRole('combobox')).toHaveLength(12)

    await fill_squad(user)
    expect(confirm_button()).toBeDisabled()
    expect(screen.getByText('Ingresá la contraseña de la liga.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Contraseña de la liga'), 'secreta')
    expect(confirm_button()).toBeEnabled()
  })

  it('sends the trimmed password together with the squad', async () => {
    join_league.mockResolvedValue({ enrollmentId: 'e-1', clubId: 'club', leagueId: LEAGUE_ID })
    const user = await mount()

    await fill_squad(user)
    await user.type(screen.getByLabelText('Contraseña de la liga'), ' secreta ')
    await user.click(confirm_button())

    expect(join_league).toHaveBeenCalledWith(LEAGUE_ID, {
      starters: [chosen(0), chosen(1), chosen(2)],
      substitutes: [chosen(3), chosen(4), chosen(5)],
      password: 'secreta',
    })
    expect(await screen.findByText(lobby_text)).toBeInTheDocument()
  })

  it('a wrong password keeps the squad and puts the cursor back on the field', async () => {
    join_league.mockRejectedValue(api_error(400, 'WRONG_LEAGUE_PASSWORD'))
    const user = await mount()

    await fill_squad(user)
    await user.type(screen.getByLabelText('Contraseña de la liga'), 'incorrecta')
    await user.click(confirm_button())

    const dialog = await screen.findByRole('dialog', { name: 'Contraseña incorrecta' })
    expect(within(dialog).getByText('La contraseña no es correcta. Revisala y volvé a confirmar.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Corregir contraseña' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña de la liga')).toHaveFocus()
    expect(screen.getByLabelText('Contraseña de la liga')).toHaveValue('incorrecta')
    expect(screen.getAllByRole('combobox')[0]).toHaveValue('player-1')
    expect(confirm_button()).toBeEnabled()
  })
})

describe('confirming', () => {
  it('joins with the selected squad and goes to the lobby', async () => {
    join_league.mockResolvedValue({ enrollmentId: 'e-1', clubId: 'club', leagueId: LEAGUE_ID })
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    expect(join_league).toHaveBeenCalledWith(LEAGUE_ID, {
      starters: [chosen(0), chosen(1), chosen(2)],
      substitutes: [chosen(3), chosen(4), chosen(5)],
    })
    expect(await screen.findByText(lobby_text)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('locks the squad and the button while the request is in flight', async () => {
    let respond
    join_league.mockReturnValue(new Promise((resolve) => { respond = resolve }))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    expect(screen.getByRole('button', { name: 'Inscribiendo…' })).toBeDisabled()
    screen.getAllByRole('combobox').forEach((select) => expect(select).toBeDisabled())

    respond({})
    expect(await screen.findByText(lobby_text)).toBeInTheDocument()
  })

  it('reports that the league is full and stops offering the selector', async () => {
    join_league.mockRejectedValue(api_error(400, 'LEAGUE_FULL'))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    const dialog = await screen.findByRole('dialog', { name: 'Liga completa' })
    expect(within(dialog).getByText('La liga está completa: ya no es posible unirse.')).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Cerrar' }))
    expect(screen.getByRole('alert')).toHaveTextContent('La liga está completa')
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
  })

  it.each([
    ['LEAGUE_NOT_OPEN', 'La liga ya no admite inscripciones.'],
    ['ALREADY_IN_LEAGUE', 'Tu club ya está inscripto en esta liga.'],
    ['LEAGUE_LIMIT_REACHED', 'Ya participás en la cantidad máxima de ligas activas.'],
  ])('shows the message for %s', async (error_code, message) => {
    join_league.mockRejectedValue(api_error(400, error_code))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    const dialog = await screen.findByRole('dialog', { name: 'No es posible unirse' })
    expect(within(dialog).getByText(message)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Volver al menú' })).toBeInTheDocument()
  })

  it('an invalid squad lets the user pick again from scratch', async () => {
    join_league.mockRejectedValue(api_error(400, 'INVALID_SQUAD'))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    const dialog = await screen.findByRole('dialog', { name: 'Escuadra no válida' })
    expect(within(dialog).getByText(/Algún jugador o comportamiento elegido/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Volver a seleccionar' }))

    await screen.findByRole('heading', { name: 'Liga del Barrio' })
    screen.getAllByRole('combobox').forEach((select) => expect(select).toHaveValue(''))
    expect(get_league).toHaveBeenCalledTimes(2)
  })

  it('a network error keeps the selection so the user can retry', async () => {
    join_league.mockRejectedValue(new TypeError('Failed to fetch'))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())

    const dialog = await screen.findByRole('dialog', { name: 'No se pudo unir a la liga' })
    expect(within(dialog).getByText('No se pudo contactar al servidor.')).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Cerrar' }))
    expect(screen.getAllByRole('combobox')[0]).toHaveValue('player-1')
    expect(confirm_button()).toBeEnabled()
  })
})

describe('live league data', () => {
  it('listens to the whole league list', async () => {
    await mount()

    expect(useLeaguesSocket).toHaveBeenCalledWith('', expect.any(Function))
  })

  it('updates the free spots when another club joins', async () => {
    await mount()

    receive_list(listed_league(6))

    expect(screen.getByText('2 de 8')).toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(12)
  })

  it('replaces the selector when the league fills up', async () => {
    await mount()

    receive_list(listed_league(8))

    expect(screen.getByRole('alert')).toHaveTextContent('La liga está completa: ya no es posible unirse.')
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
  })

  it('stops accepting clubs when the league starts', async () => {
    await mount()

    receive_list(listed_league(5, { started: true }))

    expect(screen.getByRole('alert')).toHaveTextContent('La liga ya no admite inscripciones.')
    expect(screen.getByText('En juego')).toBeInTheDocument()
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
  })

  it('a private league keeps its data because the list does not include it', async () => {
    get_league.mockResolvedValue(league({ isPrivate: true }))
    await mount()

    receive_list(listed_league(7, { id: 'other-league' }))

    expect(screen.getByText('3 de 8')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña de la liga')).toBeInTheDocument()
  })

  it('does not report a full league while the own join takes the last spot', async () => {
    get_league.mockResolvedValue(league({ enrolledClubs: 7 }))
    let respond
    join_league.mockReturnValue(new Promise((resolve) => { respond = resolve }))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())
    receive_list(listed_league(8))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Inscribiendo…' })).toBeDisabled()

    await act(async () => respond({}))

    expect(screen.getByText(lobby_text)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('reports the league as full when another club took the last spot during the join', async () => {
    get_league.mockResolvedValue(league({ enrolledClubs: 7 }))
    let reject
    join_league.mockReturnValue(new Promise((_, reject_join) => { reject = reject_join }))
    const user = await mount()

    await fill_squad(user)
    await user.click(confirm_button())
    receive_list(listed_league(8))
    await act(async () => reject(api_error(400, 'LEAGUE_FULL')))

    const dialog = screen.getByRole('dialog', { name: 'Liga completa' })
    await user.click(within(dialog).getByRole('button', { name: 'Cerrar' }))

    expect(screen.getByRole('alert')).toHaveTextContent('La liga está completa')
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)
  })
})
