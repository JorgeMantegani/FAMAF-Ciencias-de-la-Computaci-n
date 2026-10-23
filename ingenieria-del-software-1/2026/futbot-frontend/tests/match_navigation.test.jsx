import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../src/App'
import useMatchState from '../src/hooks/use_match_state'
import { get_behaviors } from '../src/api/behaviors'
import { get_friendly_room, start_friendly_match } from '../src/api/friendly_rooms'

vi.mock('../src/hooks/use_match_state', () => ({ default: vi.fn() }))
vi.mock('../src/api/behaviors', () => ({ get_behaviors: vi.fn() }))
vi.mock('../src/api/friendly_rooms', async (original) => ({ ...await original(), get_friendly_room: vi.fn(), start_friendly_match: vi.fn() }))
const state = {
  match_id: 'match-1', status: 'in_progress', revision: 1,
  home_club: { club_id: 'home', name: 'Local FC' }, away_club: { club_id: 'away', name: 'Visitante FC' },
  score: { home: 0, away: 0 }, current_time: 0, remaining_time: 120,
  ball: { x: 0, y: 0 }, actions: [],
  players: [{ player_id: 'p1', club_id: 'away', name: 'Ana', behavior_id: 'private-away', on_field: true, position: { x: 5, y: 2 } }],
}
const room = {
  status: 'readyToStart', roomCode: 'DEMO',
  homeClub: { clubId: 'home', clubName: 'Local FC', players: [] },
  awayClub: { clubId: 'away', clubName: 'Visitante FC', players: [{ playerId: 'p1', name: 'Ana', role: 'starter', behaviorId: 'private-away', behaviorName: 'Defensa rival' }] },
}

beforeEach(() => {
  vi.resetAllMocks()
  useMatchState.mockReturnValue({ state, loading: false, error: '' })
  get_behaviors.mockResolvedValue([])
  get_friendly_room.mockResolvedValue(room)
  start_friendly_match.mockResolvedValue({ matchId: 'match-1' })
})
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/') })

it.each([false, true])('abre la vista real desde la sala (ya iniciado: %s)', async (started) => {
  get_friendly_room.mockResolvedValue({ ...room, ...(started ? { status: 'inProgress', matchId: 'match-1' } : {}) })
  window.history.replaceState(null, '', '/amistosos/room-1/sala')
  render(<App />)
  await userEvent.click(await screen.findByRole('button', { name: started ? 'Ir al partido' : 'Iniciar partido' }))
  expect(window.location.pathname).toBe('/partidos/match-1')
  expect(await screen.findByRole('img', { name: /Cancha del partido/ })).toBeInTheDocument()
  expect(screen.getByText('Comportamiento: Defensa rival')).toBeInTheDocument()
  expect(screen.queryByText(/próximamente/)).not.toBeInTheDocument()
  expect(screen.queryByText('Partido amistoso')).not.toBeInTheDocument()
  expect(screen.queryByText('laboratorio / presión alta v4')).not.toBeInTheDocument()
  expect(screen.getAllByRole('banner')).toHaveLength(1)
  if (started) expect(start_friendly_match).not.toHaveBeenCalled()
  else expect(start_friendly_match).toHaveBeenCalledWith('room-1')
})

it.each(['/partidos/match-1', '/matches/match-1'])('mantiene acceso directo a %s', async (path) => {
  window.history.replaceState(null, '', path)
  render(<App />)
  expect(await screen.findByRole('img', { name: /Cancha del partido/ })).toBeInTheDocument()
  expect(useMatchState).toHaveBeenCalledWith('match-1', expect.any(Function))
})
