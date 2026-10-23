import { useCallback, useEffect, useReducer, useState } from 'react'
import { get_behaviors } from '../api/behaviors'
import { retry_match_start } from '../api/matches'
import { Link, useLocation, useParams } from 'react-router-dom'
import useMatchState from '../hooks/use_match_state'
import MatchPitch from '../components/match_pitch'
import './Match.css'

const statuses = { in_progress: 'En juego', paused: 'En pausa', finished: 'Finalizado' }
const actions = {
  movement: 'Movimiento', pass: 'Pase', shot: 'Remate', goal: 'Gol',
  substitution: 'Sustitución', behavior_changed: 'Cambio de comportamiento',
  pause: 'Pausa', resume: 'Reanudación',
}
const time = (seconds) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`
const position = (point) => point ? `(${point.x}, ${point.y})` : 'Sin posición'

// Compatibilidad con mensajes event/payload. El snapshot { type: 'state' }
// continúa siendo la fuente principal para el marcador y la ficha del partido.
const is_obj = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const is_num = (value) => typeof value === 'number' && Number.isFinite(value)
function parse_match_message(raw) {
  let message
  try { message = typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return null }
  return is_obj(message) && typeof message.event === 'string'
    ? { event: message.event, payload: is_obj(message.payload) ? message.payload : {} }
    : null
}
const normalize_player = (player) => is_obj(player) && player.playerId != null && is_num(player.x) && is_num(player.y)
  ? { id: player.playerId, club_id: player.clubId, name: player.name, x: player.x, y: player.y, is_playing: player.isPlaying !== false }
  : null
const normalize_ball = (ball) => is_obj(ball) && is_num(ball.x) && is_num(ball.y)
  ? { x: ball.x, y: ball.y, vx: is_num(ball.vx) ? ball.vx : 0, vy: is_num(ball.vy) ? ball.vy : 0 }
  : null
const normalize_score = (score) => is_obj(score) && is_num(score.home) && is_num(score.away)
  ? { home: score.home, away: score.away }
  : null
const protocol_initial_state = {
  connection: 'connecting', status: 'notStarted', role: null, current_time: 0,
  score: { home: 0, away: 0 }, ball: null, players: {}, clubs: null,
  pause: null, events: [], errors: [], received: false,
}
const remember_event = (state, event) => ({ ...state, events: [event, ...state.events].slice(0, 30) })
const protocol_players = (players) => Object.fromEntries(players.map(normalize_player).filter(Boolean).map((player) => [player.id, player]))

function protocol_reducer(state, action) {
  if (action.type === 'connection') return { ...state, connection: action.value }
  if (action.type === 'dismiss_error') return { ...state, errors: state.errors.filter((_, i) => i !== action.index) }
  if (action.type !== 'message') return state
  if (!['MATCH_CONNECTED', 'MATCH_STARTED', 'SIMULATION_TICK', 'GOAL_SCORED', 'PAUSE_STARTED', 'PAUSE_ENDED', 'CLIENT_DISCONNECTED', 'MATCH_FINISHED', 'ERROR'].includes(action.message.event)) return state
  state = { ...state, received: true }
  const { event, payload } = action.message
  switch (event) {
    case 'MATCH_CONNECTED':
      return { ...state, status: payload.status ?? state.status, role: payload.role ?? state.role,
        score: normalize_score(payload.score) ?? state.score,
        current_time: is_num(payload.currentTime) ? payload.currentTime : state.current_time,
        ball: normalize_ball(payload.ball) ?? state.ball }
    case 'MATCH_STARTED':
      return { ...state, status: state.status === 'notStarted' ? 'running' : state.status,
        clubs: { home: payload.homeClub?.clubId, away: payload.awayClub?.clubId } }
    case 'SIMULATION_TICK': {
      if (state.status === 'finished') return state
      const players = Array.isArray(payload.players) ? protocol_players(payload.players) : {}
      return { ...state, status: state.status === 'notStarted' ? 'running' : state.status,
        current_time: is_num(payload.currentTime) ? payload.currentTime : state.current_time,
        score: normalize_score(payload.score) ?? state.score, ball: normalize_ball(payload.ball) ?? state.ball,
        players: Object.keys(players).length ? players : state.players }
    }
    case 'GOAL_SCORED':
      return remember_event({ ...state, score: normalize_score(payload.score) ?? state.score,
        current_time: is_num(payload.currentTime) ? payload.currentTime : state.current_time },
      { type: 'goal', club_id: payload.clubId, player_id: payload.playerId, current_time: payload.currentTime })
    case 'PAUSE_STARTED':
      return state.status === 'finished' ? state : { ...state, status: 'paused', pause: { duration_seconds: payload.durationSeconds ?? null } }
    case 'PAUSE_ENDED': {
      if (state.status === 'finished') return state
      const substitutions = Array.isArray(payload.executedSubstitutions) ? payload.executedSubstitutions : []
      return substitutions.reduce((current, sub) => remember_event(current,
        { type: 'substitution', club_id: sub.clubId, leaving_player_id: sub.leavingPlayerId, entering_player_id: sub.enteringPlayerId }),
      { ...state, status: 'running', pause: null })
    }
    case 'CLIENT_DISCONNECTED':
      return remember_event(state, { type: 'client_disconnected', club_id: payload.clubId, message: payload.message })
    case 'MATCH_FINISHED':
      return { ...state, status: 'finished', pause: null, score: normalize_score(payload.finalScore) ?? state.score }
    case 'ERROR':
      return { ...state, errors: [{ code: payload.code, message: String(payload.message ?? 'Error de ejecución'), player_id: payload.playerId }, ...state.errors].slice(0, 5) }
    default: return state
  }
}

function MatchView({ match_id, room_behavior_names }) {
  const [protocol_state, dispatch_protocol] = useReducer(protocol_reducer, protocol_initial_state)
  const receive_protocol_message = useCallback((raw) => {
    if (raw?.type === 'connection') {
      dispatch_protocol({ type: 'connection', value: raw.value })
      return
    }
    const message = parse_match_message(raw)
    if (message) dispatch_protocol({ type: 'message', message })
  }, [])
  const { state, error, loading, waiting_for_start } = useMatchState(match_id, receive_protocol_message)
  const [retrying_start, set_retrying_start] = useState(false)
  const [start_error, set_start_error] = useState('')

  async function retry_start() {
    if (retrying_start) return
    set_retrying_start(true)
    set_start_error('')
    try {
      await retry_match_start(match_id)
    } catch (cause) {
      set_start_error(cause.message || 'No se pudo iniciar el partido.')
    } finally {
      set_retrying_start(false)
    }
  }
  const [behavior_names, set_behavior_names] = useState({})
  const has_state = Boolean(state)

  useEffect(() => {
    if (!has_state) return
    const controller = new AbortController()
    get_behaviors({ signal: controller.signal }).then((behaviors) => {
      if (controller.signal.aborted) return
      set_behavior_names(Object.fromEntries(behaviors.map(({ id, name }) => [id, name])))
    }).catch(() => {
      // El catálogo puede no incluir comportamientos privados del rival.
      // Su ausencia no debe interrumpir la transmisión del partido.
      if (!controller.signal.aborted) set_behavior_names({})
    })
    return () => controller.abort()
  }, [has_state])

  const behavior_name = (player) => player.behavior_name?.trim() || behavior_names[player.behavior_id] || room_behavior_names?.[player.behavior_id] || 'Nombre no disponible'
  const encounter = state ? `${state.home_club.name} vs. ${state.away_club.name}` : 'Estado del partido'
  return (
    <div className="match-page">
      <header className="match-header">
        <Link to="/home" className="match-brand" aria-label="FutBot · Volver al menú">
          <span className="match-brand-mark" aria-hidden="true">⚽</span>
          <span><span className="match-brand-name">FutBot</span><span className="match-brand-project" title={encounter}>{encounter}</span></span>
        </Link>
        <span className="match-connection"><i aria-hidden="true" />{error ? 'Sin sincronizar' : loading ? 'Conectando…' : 'Estado recibido'}</span>
      </header>
      <main className="match-arena">
      <h1 className="match-sr-only">Estado del partido</h1>
      {loading && <p role="status">Cargando partido…</p>}
      {error && <div className="match-warning" role="alert">{error}{state && <p>Se muestra el último estado recibido; puede estar desactualizado.</p>}</div>}
      {waiting_for_start && !state && <div>
        <button className="home-action" disabled={retrying_start} onClick={retry_start}>
          {retrying_start ? 'Iniciando…' : 'Reintentar inicio'}
        </button>
        {start_error && <p role="alert">{start_error}</p>}
      </div>}
      {state && <>
        <section className="match-scoreboard" aria-label="Marcador" aria-live="polite">
          <div className="match-score">
            <h2><i className="match-team-color match-team-color--home" aria-hidden="true" />{state.home_club.name}</h2>
            <strong aria-label={`Marcador: ${state.score.home} a ${state.score.away}`}>{state.score.home}<span>–</span>{state.score.away}</strong>
            <h2><i className="match-team-color match-team-color--away" aria-hidden="true" />{state.away_club.name}</h2>
          </div>
          <div className="match-clock"><span className={`match-status match-status--${state.status}`}>{statuses[state.status]}</span><time aria-label="Tiempo transcurrido">{time(state.current_time)}</time></div>
        </section>
        <MatchPitch state={state} protocol_state={protocol_state} />
        <div className="match-pitch-footer"><Link to="/home">← Volver al menú</Link><span>Restante: <time>{time(state.remaining_time)}</time></span></div>
        <details className="match-details">
          <summary>Jugadores y acciones del partido</summary>
        <div className="match-teams">
          {[state.home_club, state.away_club].map((club) => <section className="match-panel" key={club.club_id}>
            <h2>{club.name}</h2>
            <ul className="match-players">{state.players.filter((player) => player.club_id === club.club_id).map((player) => <li key={player.player_id}>
              <strong>{player.name}</strong><span>{player.on_field ? 'En cancha' : 'Fuera de cancha'}{player.has_ball ? ' · Con pelota' : ''}</span>
              <span>Posición: {position(player.position)}</span>
              <small>Comportamiento: {behavior_name(player)}</small>
            </li>)}</ul>
          </section>)}
        </div>
        <section className="match-panel">
          <h2>Pelota</h2><p>Posición: {position(state.ball)} · {state.ball.owner_player_id ? `Posesión: ${state.players.find((player) => player.player_id === state.ball.owner_player_id)?.name ?? 'Jugador'}` : 'Pelota libre'}</p>
        </section>
        <section className="match-panel">
          <h2>Acciones del último estado recibido</h2>
          {state.actions.length === 0 ? <p>Sin acciones en esta actualización.</p> : <ul className="match-actions">{state.actions.map((action, index) => {
            const player = state.players.find((item) => item.player_id === action.player_id)
            const club = [state.home_club, state.away_club].find((item) => item.club_id === action.club_id)
            return <li key={`${state.revision}-${index}`}><strong>{actions[action.type] ?? action.type}</strong>{player && ` · ${player.name}`}{club && ` · ${club.name}`}{action.destination && ` → ${position(action.destination)}`}</li>
          })}</ul>}
        </section>
        {(protocol_state.received || protocol_state.events.length > 0 || protocol_state.errors.length > 0) && <section className="match-panel" aria-live="polite">
          <h2>Eventos del partido</h2>
          <p>Flujo de eventos: {protocol_state.status} · {time(protocol_state.current_time)} · {protocol_state.score.home}–{protocol_state.score.away}{protocol_state.pause ? ` · Pausa: ${protocol_state.pause.duration_seconds ?? 'sin duración'} s` : ''}</p>
          {protocol_state.errors.map((item, index) => <div className="match-warning" role="alert" key={`${item.code}-${index}`}>
            {item.message}<button type="button" onClick={() => dispatch_protocol({ type: 'dismiss_error', index })} aria-label="Descartar error">×</button>
          </div>)}
          {protocol_state.events.length > 0 && <ul className="match-actions">{protocol_state.events.map((item, index) => <li key={`${item.type}-${index}`}>
            <strong>{actions[item.type] ?? item.type}</strong>{item.player_id && ` · ${item.player_id}`}{item.club_id && ` · ${item.club_id}`}{item.message && ` · ${item.message}`}
          </li>)}</ul>}
        </section>}
        </details>
      </>}
      </main>
    </div>
  )
}

export default function Match() {
  const { match_id } = useParams()
  const { state } = useLocation()
  return <MatchView key={match_id} match_id={match_id.toLowerCase()} room_behavior_names={state?.behavior_names} />
}

// Exports transitorios para que los módulos de compatibilidad y sus pruebas
// existentes usen esta implementación única.
/* eslint-disable react-refresh/only-export-components */
export {
  protocol_initial_state as initial_match_state,
  protocol_reducer as match_reducer,
  parse_match_message as parse_message,
  normalize_player,
  normalize_ball,
  normalize_score,
}
/* eslint-enable react-refresh/only-export-components */
