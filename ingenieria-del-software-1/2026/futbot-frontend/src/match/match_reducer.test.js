import { describe, expect, it } from 'vitest'
import { initial_match_state, match_reducer } from './match_reducer'

const msg = (event, payload) => ({ type: 'message', message: { event, payload } })
const player = (playerId, x, y, extra = {}) => ({ playerId, clubId: 'c1', name: playerId, x, y, isPlaying: true, ...extra })
const tick = (over = {}) =>
  msg('SIMULATION_TICK', {
    currentTime: 1,
    score: { home: 0, away: 0 },
    ball: { x: 1, y: 2, vx: 3, vy: 4 },
    players: [player('p1', 10, 5)],
    ...over,
  })
const run = (...actions) => actions.reduce(match_reducer, initial_match_state)

describe('match_reducer', () => {
  it('MATCH_CONNECTED carga el estado inicial', () => {
    const s = run(msg('MATCH_CONNECTED', { matchId: 'm1', status: 'notStarted', role: 'player', score: { home: 0, away: 1 }, currentTime: 30, ball: { x: 0, y: 0 } }))
    expect(s).toMatchObject({ status: 'notStarted', role: 'player', score: { home: 0, away: 1 }, current_time: 30 })
    expect(s.ball).toEqual({ x: 0, y: 0, vx: 0, vy: 0 })
  })

  it('SIMULATION_TICK actualiza jugadores, pelota, tiempo y arranca el partido', () => {
    const s = run(tick())
    expect(s.status).toBe('running')
    expect(s.players.p1).toMatchObject({ x: 10, y: 5, club_id: 'c1', is_playing: true })
    expect(s.ball).toEqual({ x: 1, y: 2, vx: 3, vy: 4 })
    expect(s.current_time).toBe(1)
  })

  it('ticks sucesivos reemplazan el estado completo', () => {
    const s = run(tick(), tick({ currentTime: 2, players: [player('p1', 12, 6), player('p2', 0, 0)] }), tick({ currentTime: 3, players: [player('p2', 1, 1)] }))
    expect(s.current_time).toBe(3)
    expect(s.players.p1).toBeUndefined()
    expect(s.players.p2).toMatchObject({ x: 1, y: 1 })
  })

  it('GOAL_SCORED actualiza el marcador y registra el gol', () => {
    const s = run(tick(), msg('GOAL_SCORED', { clubId: 'c1', playerId: 'p1', score: { home: 1, away: 0 }, currentTime: 40 }))
    expect(s.score).toEqual({ home: 1, away: 0 })
    expect(s.events[0]).toMatchObject({ type: 'goal', player_id: 'p1', club_id: 'c1' })
  })

  it('MATCH_STARTED guarda qué club es local y cuál visitante', () => {
    const s = run(msg('MATCH_STARTED', { assignedAutomatically: false, homeClub: { clubId: 'h' }, awayClub: { clubId: 'a' } }))
    expect(s.clubs).toEqual({ home: 'h', away: 'a' })
    expect(s.status).toBe('running')
  })

  it('pausa: PAUSE_STARTED / PAUSE_ENDED con sustituciones ejecutadas', () => {
    let s = run(tick(), msg('PAUSE_STARTED', { currentTime: 100, durationSeconds: 30 }))
    expect(s.status).toBe('paused')
    expect(s.pause).toEqual({ duration_seconds: 30 })
    s = match_reducer(s, msg('PAUSE_ENDED', { currentTime: 130, executedSubstitutions: [{ leavingPlayerId: 'p1', enteringPlayerId: 'p9', clubId: 'c1' }] }))
    expect(s.status).toBe('running')
    expect(s.pause).toBeNull()
    expect(s.events[0]).toMatchObject({ type: 'substitution', entering_player_id: 'p9' })
  })

  it('CLIENT_DISCONNECTED se registra como evento', () => {
    const s = run(msg('CLIENT_DISCONNECTED', { clubId: 'c2', message: 'bot al mando' }))
    expect(s.events[0]).toMatchObject({ type: 'client_disconnected', club_id: 'c2' })
  })

  it('un error no destruye el último estado válido', () => {
    const s = run(tick(), msg('ERROR', { code: 'EXEC_FAILED', message: 'timeout', playerId: 'p1' }))
    expect(s.errors).toHaveLength(1)
    expect(s.errors[0]).toMatchObject({ code: 'EXEC_FAILED', player_id: 'p1' })
    expect(s.players.p1).toBeDefined()
    expect(s.status).toBe('running')
  })

  it('ignora eventos desconocidos y datos mal formados', () => {
    const s = run(tick(), msg('ALGO_RARO', {}), tick({ currentTime: 'x', score: 5, ball: 'x', players: [{ playerId: 'p1', x: 'NaN' }] }))
    expect(s.players.p1).toMatchObject({ x: 10, y: 5 })
    expect(s.ball).toMatchObject({ x: 1, y: 2 })
    expect(s.score).toEqual({ home: 0, away: 0 })
    expect(s.current_time).toBe(1)
  })

  it('MATCH_FINISHED termina el partido y los ticks tardíos no lo reabren', () => {
    const s = run(tick(), msg('MATCH_FINISHED', { finalScore: { home: 2, away: 1 }, matchId: 'm1' }), tick({ currentTime: 99 }))
    expect(s.status).toBe('finished')
    expect(s.score).toEqual({ home: 2, away: 1 })
    expect(s.current_time).toBe(1)
  })
})