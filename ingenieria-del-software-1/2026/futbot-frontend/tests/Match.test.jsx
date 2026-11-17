import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Match from '../src/pages/Match'
import { connect_match_state, retry_match_start } from '../src/api/matches'
import { get_behaviors } from '../src/api/behaviors'
import { save_session } from '../src/auth/session'

vi.mock('../src/api/behaviors', () => ({ get_behaviors: vi.fn() }))
vi.mock('../src/api/matches', () => ({ connect_match_state: vi.fn(), retry_match_start: vi.fn() }))
const snapshot = (changes = {}) => ({
  match_id: 'match-1', revision: 1, status: 'in_progress', phase: 'PLAYING', pause_duration: null, pause_remaining: null,
  home_club: { club_id: 'home', name: 'Local FC' }, away_club: { club_id: 'away', name: 'Visitante FC' },
  score: { home: 0, away: 0 }, current_time: 5, remaining_time: 295,
  ball: { x: 10, y: 20, owner_player_id: null },
  players: [
    { player_id: 'p1', club_id: 'home', name: 'Jugador 01', behavior_id: 'b1', on_field: true, has_ball: false, position: { x: 5, y: 3 } },
    { player_id: 'p2', club_id: 'home', name: 'Jugador 02', behavior_id: 'b1', behavior_name: 'Volante', on_field: true, has_ball: false, position: { x: 8, y: 4 } },
    { player_id: 'p3', club_id: 'home', name: 'Jugador 03', behavior_id: 'b1', behavior_name: 'Defensor', on_field: true, has_ball: false, position: { x: 10, y: 6 } },
    { player_id: 'p4', club_id: 'home', name: 'Jugador 04', behavior_id: 'b1', behavior_name: 'Arquero', on_field: false, has_ball: false, position: null },
    { player_id: 'p5', club_id: 'home', name: 'Jugador 05', behavior_id: 'b1', behavior_name: 'Delantero', on_field: false, has_ball: false, position: null },
  ],
  actions: [], ...changes,
})
const mount = () => render(<MemoryRouter initialEntries={['/matches/match-1']}><Routes>
  <Route path="/matches/:match_id" element={<Match />} />
  <Route path="/login" element={<p>Inicio de sesión</p>} />
</Routes></MemoryRouter>)
class Socket {
  readyState = 1
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

  it('mantiene disponible la acción de sustituir durante un partido en juego', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state({ status: 'in_progress' }) })
    expect(screen.getByRole('button', { name: 'Sustituir' })).toBeEnabled()
    await emit(() => sockets[0].state({ revision: 2, status: 'paused' }))
    expect(screen.getByRole('button', { name: 'Sustituir' })).toBeEnabled()
  })

  it('envía la solicitud y muestra el cambio planificado al recibir el evento WebSocket', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Sustituir' })))
    await emit(() => {
      fireEvent.click(screen.getByRole('button', { name: /Jugador 01/ }))
      fireEvent.click(screen.getByRole('button', { name: /Jugador 04/ }))
    })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: /Confirmar cambio/ })))
    expect(sockets[0].send).toHaveBeenCalledWith(JSON.stringify({
      type: 'SUBSTITUTE_PLAYER', outPlayerId: 'p1', inPlayerId: 'p4',
    }))

    await emit(() => sockets[0].message({
      type: 'SUBSTITUTION_SCHEDULED', team: 'home', outPlayerId: 'p1', inPlayerId: 'p4',
    }))
    expect(screen.getByText(/Cambio planificado para la próxima pausa:/)).toBeInTheDocument()
    expect(document.querySelector('.substitution-scheduled')).toHaveTextContent('Jugador 01 por Jugador 04')
    expect(screen.getByText('Sustitución planificada para la siguiente pausa')).toBeInTheDocument()
  })

  it('bloquea el envío al agotar el cupo de la pausa y lo restablece al reanudar', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state({ status: 'paused' }) })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Sustituir' })))
    await emit(() => sockets[0].message({
      type: 'SUBSTITUTION_APPLIED', team: 'home', outPlayerId: 'p1', inPlayerId: 'p4',
    }))
    expect(screen.getByText('Límite alcanzado: 1 cambio por pausa')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Confirmar cambio/ })).toBeDisabled()

    const starter_list = screen.getByRole('region', { name: 'Titular que sale' })
    const substitute_list = screen.getByRole('region', { name: 'Suplente que entra' })
    expect(within(starter_list).getByRole('button', { name: /Jugador 04/ })).toBeInTheDocument()
    expect(within(substitute_list).getByRole('button', { name: /Jugador 01/ })).toBeInTheDocument()
    await emit(() => {
      fireEvent.click(within(starter_list).getByRole('button', { name: /Jugador 04/ }))
      fireEvent.click(within(substitute_list).getByRole('button', { name: /Jugador 01/ }))
    })
    expect(screen.getByRole('button', { name: /Confirmar cambio/ })).toBeDisabled()

    await emit(() => sockets[0].message({ type: 'MATCH_RESUMED' }))
    expect(screen.queryByText('Límite alcanzado: 1 cambio por pausa')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Confirmar cambio/ })).toBeEnabled()
  })

  it('solo muestra eventos de sustitución del equipo propio y no limpia su solicitud', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Sustituir' })))
    await emit(() => {
      fireEvent.click(screen.getByRole('button', { name: /Jugador 01/ }))
      fireEvent.click(screen.getByRole('button', { name: /Jugador 04/ }))
    })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: /Confirmar cambio/ })))

    await emit(() => sockets[0].message({
      type: 'SUBSTITUTION_SCHEDULED', team: 'away', outPlayerId: 'a1', inPlayerId: 'a4',
    }))
    await emit(() => sockets[0].message({
      type: 'SUBSTITUTION_APPLIED', team: 'away', outPlayerId: 'a1', inPlayerId: 'a4',
    }))
    await emit(() => sockets[0].message({
      type: 'error', team: 'away', error_code: 'SUBSTITUTION_LIMIT_REACHED', message: 'Límite rival',
    }))

    expect(screen.getByRole('button', { name: /Enviando/ })).toBeInTheDocument()
    expect(document.querySelector('.substitution-scheduled')).toBeNull()
    expect(document.querySelector('.substitution-limit')).toBeNull()
    expect(document.querySelector('.substitution-error')).toBeNull()
    expect(screen.queryByText('Sustitución planificada para la siguiente pausa')).not.toBeInTheDocument()
    expect(screen.queryByText('Sustitución efectuada')).not.toBeInTheDocument()
  })

  it('detecta el límite por error_code y no por la redacción del mensaje', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state({ status: 'paused' }) })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Sustituir' })))
    await emit(() => {
      fireEvent.click(screen.getByRole('button', { name: /Jugador 01/ }))
      fireEvent.click(screen.getByRole('button', { name: /Jugador 04/ }))
    })
    await emit(() => sockets[0].message({
      type: 'error',
      team: 'home',
      error_code: 'SUBSTITUTION_LIMIT_REACHED',
      message: 'El cupo disponible ya fue utilizado',
    }))

    expect(document.querySelector('.substitution-limit')).toHaveTextContent('Límite alcanzado')
    expect(document.querySelector('.substitution-error')).toHaveTextContent('El cupo disponible ya fue utilizado')
    expect(screen.getByRole('button', { name: /Confirmar cambio/ })).toBeDisabled()
  })

  it('aisla el duelo de penales y actualiza el marcador de aciertos y fallos', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state({ status: 'paused' }) })
    await emit(() => sockets[0].message({
      type: 'PENALTIES_STARTED', maxAttemptsPerTeam: 5, maxSecondsPerAttempt: 10, tickRate: 10,
    }))
    await emit(() => sockets[0].state({
      revision: 2,
      status: 'paused',
      players: snapshot().players.map((player, index) => ({
        ...player,
        on_field: index < 2,
        position: index < 2 ? player.position : null,
      })),
    }))

    expect(screen.getByRole('heading', { name: 'Tanda de penales' })).toBeInTheDocument()
    const duel_players = Array.from(document.querySelectorAll('.match-pitch-player'))
    expect(duel_players).toHaveLength(2)
    expect(duel_players.map((player) => player.querySelector('title').textContent))
      .toEqual(expect.arrayContaining(['Jugador 01 · Local FC', 'Jugador 02 · Local FC']))
    expect(screen.getAllByLabelText(/Penal [1-5]: pendiente/)).toHaveLength(10)

    await emit(() => sockets[0].message({
      type: 'PENALTY_SHOT_RESULT',
      status: 'scored',
      team: 'HOME',
      attempts: { HOME: 1, AWAY: 0 },
      score: { HOME: 1, AWAY: 0 },
      shooterId: 'p1',
      goalkeeperId: 'p2',
    }))
    expect(screen.getByLabelText('Penal 1: gol')).toHaveClass('penalty-attempt--scored')
    expect(screen.getByLabelText('Local FC: 1 goles')).toBeInTheDocument()

    await emit(() => sockets[0].message({
      type: 'PENALTY_SHOT_RESULT',
      status: 'missed',
      team: 'AWAY',
      attempts: { HOME: 1, AWAY: 1 },
      score: { HOME: 1, AWAY: 0 },
      shooterId: 'p2',
      goalkeeperId: 'p1',
    }))
    expect(screen.getByLabelText('Penal 1: fallo')).toHaveClass('penalty-attempt--missed')
    expect(screen.getByLabelText('Visitante FC: 0 goles')).toBeInTheDocument()
  })

  it('cuenta atrás desde el tiempo anunciado por el backend y reinicia al siguiente penal', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state({ status: 'paused' }) })
    await emit(() => sockets[0].message({
      type: 'PENALTIES_STARTED', maxAttemptsPerTeam: 5, maxSecondsPerAttempt: 10, tickRate: 10,
    }))
    expect(screen.getByLabelText('Tiempo restante del penal')).toHaveTextContent('10')
    await emit(() => sockets[0].state({ revision: 31, status: 'paused' }))
    expect(screen.getByLabelText('Tiempo restante del penal')).toHaveTextContent('7')
    await emit(() => sockets[0].state({ revision: 101, status: 'paused' }))
    expect(screen.getByLabelText('Tiempo restante del penal')).toHaveTextContent('0')

    await emit(() => sockets[0].message({
      type: 'PENALTY_SHOT_RESULT',
      status: 'missed',
      team: 'HOME',
      attempts: { HOME: 1, AWAY: 0 },
      score: { HOME: 0, AWAY: 0 },
    }))
    expect(screen.getByLabelText('Tiempo restante del penal')).toHaveTextContent('10')
  })

  it('conserva el último estado al desconectarse y recupera el snapshot al reconectar', async () => {
    mount()
    await emit(() => sockets[0].state())
    await emit(() => sockets[0].fail())
    expect(screen.getByRole('alert')).toHaveTextContent('desactualizado')
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    await tick()
    expect(sockets).toHaveLength(2)
    await emit(() => sockets[1].state({ revision: 2, status: 'paused', phase: 'HYDRATION', pause_duration: 15, pause_remaining: 15 }))
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
  
  it('envía CHANGE_BEHAVIOR por el socket al confirmar el modal', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Cambiar comportamiento' })))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Jugador 01'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Confirmar' })))
    expect(sockets[0].send).toHaveBeenCalledWith(
      JSON.stringify({ action: 'CHANGE_BEHAVIOR', payload: { playerId: 'p1', behaviorId: 'b2' } }),
    )
  })

  it('un error tras CHANGE_BEHAVIOR no corta la vista del partido', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Cambiar comportamiento' })))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Jugador 01'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Confirmar' })))
    await emit(() => sockets[0].message({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE', message: 'Comportamiento no disponible' }))
    expect(sockets[0].close).not.toHaveBeenCalled()
    expect(screen.queryByText('El partido no existe.')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
  })

  it('cierra el modal y muestra un aviso de éxito al recibir el acuse', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Cambiar comportamiento' })))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Jugador 01'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Confirmar' })))
    await emit(() => sockets[0].message({ event: 'BEHAVIOR_CHANGED', payload: { playerId: 'p1', behaviorId: 'b2' } }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Comportamiento actualizado')
  })

  it('muestra el error del servidor en un aviso y deja el modal abierto', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Cambiar comportamiento' })))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Jugador 01'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Confirmar' })))
    await emit(() => sockets[0].message({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE', message: 'Comportamiento no disponible' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Comportamiento no disponible')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('ignora SUBSTITUTION_STATE sin romper la vista ni mostrar avisos', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => sockets[0].message({ type: 'SUBSTITUTION_STATE' }))
    expect(screen.getByLabelText('Marcador: 0 a 0')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('con varios cambios seguidos, un error posterior al primer acuse no corta la vista', async () => {
    mount()
    const players = [
      snapshot().players[0],
      { ...snapshot().players[0], player_id: 'p2', name: 'Beto' },
    ]
    await emit(() => { sockets[0].open(); sockets[0].state({ players }) })
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Cambiar comportamiento' })))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Jugador 01'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.change(screen.getByLabelText('Comportamiento de Beto'), { target: { value: 'b2' } }))
    await emit(() => fireEvent.click(screen.getByRole('button', { name: 'Confirmar' })))
    await emit(() => sockets[0].message({ event: 'BEHAVIOR_CHANGED', payload: { playerId: 'p1', behaviorId: 'b2' } }))
    await emit(() => sockets[0].message({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE', message: 'Comportamiento no disponible' }))
    expect(sockets[0].close).not.toHaveBeenCalled()
    expect(screen.queryByText('El partido no existe.')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Comportamiento no disponible')
  })
  it('un error con error_code del cambio de comportamiento nunca es terminal', async () => {
    mount()
    await emit(() => { sockets[0].open(); sockets[0].state() })
    await emit(() => sockets[0].message({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_MATCH_NOT_RUNNING', message: 'El partido no está en curso' }))
    expect(sockets[0].close).not.toHaveBeenCalled()
    expect(screen.queryByText('El partido no existe.')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('El partido no está en curso')
  })
})

describe('Banner de pausa', () => {
  const paused = (changes = {}) => ({ status: 'paused', phase: 'HYDRATION', pause_duration: 15, pause_remaining: 15, current_time: 75, ...changes })
  const banner = (name) => screen.queryByRole('region', { name })
  const countdown = () => screen.getByLabelText('Tiempo restante de la pausa')

  it('muestra la pausa con la duración del backend y la quita al reanudarse', async () => {
    mount()
    await emit(() => sockets[0].state())
    expect(banner('Pausa de hidratación')).not.toBeInTheDocument()
    await emit(() => sockets[0].state(paused({ revision: 2 })))
    expect(banner('Pausa de hidratación')).toBeInTheDocument()
    expect(countdown()).toHaveTextContent('15 s')
    await tick(3000)
    await emit(() => sockets[0].state(paused({ revision: 3, pause_remaining: 12 })))
    expect(countdown()).toHaveTextContent('12 s')
    await emit(() => sockets[0].state({ revision: 4, current_time: 76 }))
    expect(banner('Pausa de hidratación')).not.toBeInTheDocument()
  })

  it('arranca en el tiempo restante al entrar a un partido ya pausado', async () => {
    mount()
    await emit(() => sockets[0].state(paused({ phase: 'HALFTIME', current_time: 150, pause_remaining: 5 })))
    expect(banner('Entretiempo')).toBeInTheDocument()
    expect(countdown()).toHaveTextContent('5 s')
  })

  it('sigue contando mientras se reconecta en medio de la pausa', async () => {
    mount()
    await emit(() => sockets[0].state(paused()))
    await tick(2000)
    await emit(() => sockets[0].fail())
    expect(banner('Pausa de hidratación')).toBeInTheDocument()
    await tick(1000)
    expect(sockets).toHaveLength(2)
    expect(countdown()).toHaveTextContent('12 s')
    await emit(() => sockets[1].state(paused({ revision: 2, pause_remaining: 12 })))
    expect(countdown()).toHaveTextContent('12 s')
  })

  it('reinicia la cuenta en una pausa nueva aunque no llegue el juego intermedio', async () => {
    mount()
    await emit(() => sockets[0].state(paused()))
    await tick(10000)
    expect(countdown()).toHaveTextContent('5 s')
    await emit(() => sockets[0].state(paused({ revision: 2, phase: 'HALFTIME', current_time: 150 })))
    expect(banner('Entretiempo')).toBeInTheDocument()
    expect(countdown()).toHaveTextContent('15 s')
  })
})
