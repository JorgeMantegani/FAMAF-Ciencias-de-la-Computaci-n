import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Match from '../src/pages/Match'
import { connect_match_state, retry_match_start } from '../src/api/matches'
import { get_behaviors } from '../src/api/behaviors'
import { save_session } from '../src/auth/session'

vi.mock('../src/api/behaviors', () => ({ get_behaviors: vi.fn() }))
vi.mock('../src/api/matches', () => ({ connect_match_state: vi.fn(), retry_match_start: vi.fn() }))
const snapshot = (changes = {}) => ({
  match_id: 'match-1', revision: 1, status: 'in_progress',
  home_club: { club_id: 'home', name: 'Local FC' }, away_club: { club_id: 'away', name: 'Visitante FC' },
  score: { home: 0, away: 0 }, current_time: 5, remaining_time: 295,
  ball: { x: 10, y: 20, owner_player_id: null },
  players: [{ player_id: 'p1', club_id: 'home', name: 'Ana', behavior_id: 'b1', on_field: true, has_ball: false, position: { x: 5, y: 3 } }],
  actions: [], ...changes,
})
const mount = () => render(<MemoryRouter initialEntries={['/matches/match-1']}><Routes>
  <Route path="/matches/:match_id" element={<Match />} />
  <Route path="/login" element={<p>Inicio de sesión</p>} />
</Routes></MemoryRouter>)
class Socket {
  send = vi.fn()
  close = vi.fn()
  open() { this.onopen?.() }
  message(message) { this.onmessage?.({ data: JSON.stringify(message) }) }
  state(changes = {}) { this.message({ type: 'state', state: snapshot(changes) }) }
  fail() { this.onclose?.({ code: 1006 }) }
}
let sockets
const emit = async (callback) => act(async () => callback())
const tick = async (ms = 1000) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  get_behaviors.mockResolvedValue([{ id: 'b1', name: 'Defensa' }, { id: 'b2', name: 'Ataque' }])
  sockets = []
  connect_match_state.mockImplementation(() => {
    const socket = new Socket()
    sockets.push(socket)
    return socket
  })
  save_session({ access_token: 'token', refresh_token: 'refresh', club_id: 'home', expires_at: Date.now() / 1000 + 3600 })
})
afterEach(() => { cleanup(); vi.useRealTimers(); localStorage.clear(); sessionStorage.clear() })

describe('Estado del partido por WebSocket', () => {
  it('permite reintentar un partido sin estado y muestra la cancha al recibirlo', async () => {
    retry_match_start.mockResolvedValue({ status: 'started' })
    mount()
    await emit(() => sockets[0].message({ type: 'error', status: 409 }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Reintentar inicio' })))
    expect(retry_match_start).toHaveBeenCalledWith('match-1')
    await emit(() => sockets[0].state())
    expect(screen.queryByRole('button', { name: 'Reintentar inicio' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
  })

  it('muestra el error si no se puede reintentar el inicio', async () => {
    retry_match_start.mockRejectedValue(new Error('No tenes acceso a este partido'))
    mount()
    await emit(() => sockets[0].message({ type: 'error', status: 409 }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Reintentar inicio' })))
    expect(screen.getByText('No tenes acceso a este partido')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar inicio' })).toBeEnabled()
  })

  it('autentica y actualiza marcador, cancha y acciones sin abrir más conexiones', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    expect(sockets[0].send).toHaveBeenCalledWith(JSON.stringify({ type: 'auth', token: 'token' }))
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    const marker = document.querySelector('.match-pitch-player')
    const initial_position = marker.getAttribute('transform')
    await emit(() => sockets[0].state({
      revision: 2, score: { home: 1, away: 0 }, current_time: 42, remaining_time: 258,
      actions: [{ type: 'goal', player_id: 'p1', club_id: 'home' }],
      players: [{ ...snapshot().players[0], position: { x: 12, y: 8 }, has_ball: true, behavior_id: 'b2' }],
    }))
    expect(screen.getByLabelText('Marcador: 1 a 0')).toBeInTheDocument()
    expect(screen.getByText('00:42')).toBeInTheDocument()
    expect(screen.getByText('Gol')).toBeInTheDocument()
    expect(screen.getByText('Comportamiento: Ataque')).toBeInTheDocument()
    expect(marker.getAttribute('transform')).not.toBe(initial_position)
    expect(marker.querySelector('.match-possession-ring')).not.toBeNull()
    await tick(3000)
    expect(connect_match_state).toHaveBeenCalledTimes(1)
    await emit(() => sockets[0].state({ revision: 3, status: 'finished' }))
    expect(screen.getByText('Finalizado')).toBeInTheDocument()
    expect(sockets[0].close).toHaveBeenCalled()
    await tick(60000)
    expect(connect_match_state).toHaveBeenCalledTimes(1)
  })

  it('conserva el último estado al desconectarse y recupera el snapshot al reconectar', async () => {
    mount()
    await emit(() => sockets[0].state())
    await emit(() => sockets[0].fail())
    expect(screen.getByRole('alert')).toHaveTextContent('desactualizado')
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    await tick()
    expect(sockets).toHaveLength(2)
    await emit(() => sockets[1].state({ revision: 2, status: 'paused' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('En pausa')).toBeInTheDocument()
  })

  it('espera el estado inicial en la misma conexión y descarta revisiones antiguas', async () => {
    mount()
    await emit(() => sockets[0].message({ type: 'error', status: 409 }))
    expect(screen.getByRole('alert')).toHaveTextContent('Esperando el estado inicial')
    await emit(() => sockets[0].state({ revision: 3, score: { home: 2, away: 0 } }))
    await emit(() => sockets[0].state())
    expect(screen.getByLabelText('Marcador: 2 a 0')).toBeInTheDocument()
    expect(sockets).toHaveLength(1)
  })

  it.each([403, 404, 422])('no reconecta ante un error terminal %s', async (status) => {
    mount()
    await emit(() => sockets[0].message({ type: 'error', status }))
    await tick(60000)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(connect_match_state).toHaveBeenCalledTimes(1)
    expect(sockets[0].close).toHaveBeenCalled()
  })

  it('redirige sin sesión y borra una sesión rechazada por el servidor', async () => {
    mount()
    await emit(() => sockets[0].message({ type: 'error', status: 401 }))
    expect(screen.getByText('Inicio de sesión')).toBeInTheDocument()
    expect(localStorage.getItem('futbot.session')).toBeNull()
    cleanup(); connect_match_state.mockClear()
    mount()
    expect(screen.getByText('Inicio de sesión')).toBeInTheDocument()
    expect(connect_match_state).not.toHaveBeenCalled()
  })

  it('contesta heartbeat sin consultar el estado y reconecta una conexión silenciosa', async () => {
    mount()
    await emit(() => sockets[0].state())
    await tick(30000)
    await emit(() => sockets[0].message({ type: 'ping' }))
    expect(sockets[0].send).toHaveBeenCalledWith('{"type":"pong"}')
    await tick(30000)
    expect(sockets).toHaveLength(1)
    await tick(16000)
    expect(sockets).toHaveLength(2)
  })

  it('maneja un estado inválido sin romper la pantalla', async () => {
    mount()
    await emit(() => sockets[0].state())
    await emit(() => sockets[0].message({ type: 'state', state: { match_id: 'otro' } }))
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    await tick()
    expect(sockets).toHaveLength(2)
  })

  it('cierra la conexión cuando vence la sesión', async () => {
    save_session({ access_token: 'token', refresh_token: 'refresh', club_id: 'home', expires_at: Date.now() / 1000 + 2 })
    mount()
    await emit(() => sockets[0].state())
    await tick(2000)
    expect(screen.getByText('Inicio de sesión')).toBeInTheDocument()
    expect(sockets[0].close).toHaveBeenCalled()
  })

  it('consulta el catálogo una vez y muestra nombres en las actualizaciones', async () => {
    mount()
    await emit(() => sockets[0].state())
    expect(screen.getByText('Comportamiento: Defensa')).toBeInTheDocument()
    await emit(() => sockets[0].state({ revision: 2 }))
    expect(get_behaviors).toHaveBeenCalledTimes(1)
  })

  it('conserva el partido si falla el catálogo y no muestra UUID como nombre', async () => {
    get_behaviors.mockRejectedValue(new Error('Catálogo no disponible'))
    mount()
    await emit(() => sockets[0].state())
    expect(screen.getByText('Comportamiento: Nombre no disponible')).toBeInTheDocument()
    expect(screen.queryByText('Comportamiento: b1')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    await emit(() => sockets[0].state({ revision: 2, players: [{ ...snapshot().players[0], behavior_name: 'Pase corto' }] }))
    expect(screen.getByText('Comportamiento: Pase corto')).toBeInTheDocument()
  })

  it('limpia conexiones y reintentos al desmontar', async () => {
    const view = mount()
    await emit(() => sockets[0].fail())
    view.unmount()
    await tick(60000)
    expect(sockets).toHaveLength(1)
    expect(sockets[0].onmessage).toBeNull()
    expect(sockets[0].close).toHaveBeenCalled()
  })
})
