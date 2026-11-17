import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { get_behaviors } from '../api/behaviors'
import { retry_match_start } from '../api/matches'
import { read_session } from '../auth/session'
import { Link, useLocation, useParams } from 'react-router-dom'
import useMatchState from '../hooks/use_match_state'
import PauseBanner from '../components/pause_banner'
import MatchPitch from '../components/match_pitch'
import ChangeBehaviorModal from '../components/change_behavior_modal'
import { build_change_behavior_message } from '../match/change_behavior_message'
import { get_my_starters } from '../match/my_starters'
import Toast from '../components/toast'
import { parse_change_result } from '../match/change_behavior_result'
import PenaltyShootout from '../components/PenaltyShootout'
import LiveMatchControls from '../components/LiveMatchControls'
import SubstitutionModal from '../components/SubstitutionModal'
import './Match.css'

const statuses = { in_progress: 'En juego', paused: 'En pausa', finished: 'Finalizado' }
const actions = {
  movement: 'Movimiento', pass: 'Pase', shot: 'Remate', goal: 'Gol',
  substitution: 'Sustitución', behavior_changed: 'Cambio de comportamiento',
  pause: 'Pausa', resume: 'Reanudación',
}
const time = (seconds) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`
const position = (point) => point ? `(${point.x}, ${point.y})` : 'Sin posición'

// Compatibilidad con mensajes event/payload y eventos WebSocket de nivel superior.
// El snapshot { type: 'state' } continúa siendo la fuente del estado del partido.
const is_obj = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const is_num = (value) => typeof value === 'number' && Number.isFinite(value)
const normalize_player = (player) => is_obj(player) && player.playerId != null && is_num(player.x) && is_num(player.y)
  ? { id: player.playerId, club_id: player.clubId, name: player.name, x: player.x, y: player.y, is_playing: player.isPlaying !== false }
  : null
const normalize_ball = (ball) => is_obj(ball) && is_num(ball.x) && is_num(ball.y)
  ? { x: ball.x, y: ball.y, vx: is_num(ball.vx) ? ball.vx : 0, vy: is_num(ball.vy) ? ball.vy : 0 }
  : null
const normalize_score = (score) => is_obj(score) && is_num(score.home) && is_num(score.away)
  ? { home: score.home, away: score.away }
  : null
const normalize_team = (team) => typeof team === 'string' && ['HOME', 'AWAY'].includes(team.toUpperCase())
  ? team.toUpperCase()
  : null
const protocol_initial_state = {
  connection: 'connecting', status: 'notStarted', role: null, current_time: 0,
  score: { home: 0, away: 0 }, ball: null, players: {}, clubs: null,
  pause: null, events: [], errors: [], received: false, toast: '',
  pending_substitutions: { HOME: null, AWAY: null },
  changes_used_this_pause: { HOME: false, AWAY: false },
  substitution_last_applied: null,
  penalties: { active: false, completed: false, attempts: { HOME: 0, AWAY: 0 },
    scores: { HOME: 0, AWAY: 0 }, results: { HOME: [], AWAY: [] },
    max_attempts: 5, max_seconds_per_attempt: 10, tick_rate: 1,
    start_revision: null, winner: null },
}
const remember_event = (state, event) => ({ ...state, events: [event, ...state.events].slice(0, 30) })
const protocol_players = (players) => Object.fromEntries(players.map(normalize_player).filter(Boolean).map((player) => [player.id, player]))

function parse_match_message(raw) {
  let message
  try { message = typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return null }
  if (!is_obj(message)) return null
  if (typeof message.event === 'string') {
    return { event: message.event, payload: is_obj(message.payload) ? message.payload : {} }
  }
  const event = message.type === 'error' ? 'ERROR' : message.type
  return [
    'MATCH_CONNECTED', 'MATCH_STARTED', 'SIMULATION_TICK', 'GOAL_SCORED',
    'PAUSE_STARTED', 'PAUSE_ENDED', 'MATCH_RESUMED', 'CLIENT_DISCONNECTED',
    'MATCH_FINISHED', 'ERROR', 'SUBSTITUTION_SCHEDULED', 'SUBSTITUTION_APPLIED',
    'PENALTIES_STARTED', 'PENALTY_SHOT_RESULT', 'PENALTIES_FINISHED',
  ].includes(event)
    ? { event, payload: message }
    : null
}

function protocol_reducer(state, action) {
  if (action.type === 'connection') return { ...state, connection: action.value }
  if (action.type === 'dismiss_error') return { ...state, errors: state.errors.filter((_, i) => i !== action.index) }
  if (action.type === 'dismiss_toast') return { ...state, toast: '' }
  if (action.type !== 'message') return state
  if (![
    'MATCH_CONNECTED', 'MATCH_STARTED', 'SIMULATION_TICK', 'GOAL_SCORED',
    'PAUSE_STARTED', 'PAUSE_ENDED', 'MATCH_RESUMED', 'CLIENT_DISCONNECTED',
    'MATCH_FINISHED', 'ERROR', 'SUBSTITUTION_SCHEDULED', 'SUBSTITUTION_APPLIED',
    'PENALTIES_STARTED', 'PENALTY_SHOT_RESULT', 'PENALTIES_FINISHED',
  ].includes(action.message.event)) return state
  state = { ...state, received: true }
  const { event, payload } = action.message
  const team = normalize_team(payload.team)
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
    case 'SUBSTITUTION_SCHEDULED': {
      const pending_substitutions = team
        ? { ...state.pending_substitutions, [team]: { outPlayerId: payload.outPlayerId, inPlayerId: payload.inPlayerId } }
        : state.pending_substitutions
      return remember_event({
        ...state,
        pending_substitutions,
        toast: team === action.own_team ? 'Sustitución planificada para la siguiente pausa' : state.toast,
      }, { type: 'substitution_scheduled', team, leaving_player_id: payload.outPlayerId, entering_player_id: payload.inPlayerId })
    }
    case 'SUBSTITUTION_APPLIED': {
      const pending_substitutions = team
        ? { ...state.pending_substitutions, [team]: null }
        : state.pending_substitutions
      const changes_used_this_pause = team
        ? { ...state.changes_used_this_pause, [team]: true }
        : state.changes_used_this_pause
      return remember_event({
        ...state,
        pending_substitutions,
        changes_used_this_pause,
        substitution_last_applied: team === action.own_team
          ? { team, outPlayerId: payload.outPlayerId, inPlayerId: payload.inPlayerId }
          : state.substitution_last_applied,
        toast: team === action.own_team ? 'Sustitución efectuada' : state.toast,
      }, { type: 'substitution', team, leaving_player_id: payload.outPlayerId, entering_player_id: payload.inPlayerId })
    }
    case 'MATCH_RESUMED':
      return { ...state, status: 'running', pause: null,
        pending_substitutions: { HOME: null, AWAY: null },
        changes_used_this_pause: { HOME: false, AWAY: false } }
    case 'CLIENT_DISCONNECTED':
      return remember_event(state, { type: 'client_disconnected', club_id: payload.clubId, message: payload.message })
    case 'MATCH_FINISHED':
      return { ...state, status: 'finished', pause: null, score: normalize_score(payload.finalScore) ?? state.score }
    case 'PENALTIES_STARTED':
      return {
        ...state,
        status: 'paused',
        penalties: {
          ...protocol_initial_state.penalties,
          active: true,
          start_revision: Number.isInteger(action.server_revision) ? action.server_revision : null,
          max_attempts: Number.isInteger(payload.maxAttemptsPerTeam) && payload.maxAttemptsPerTeam > 0
            ? payload.maxAttemptsPerTeam : protocol_initial_state.penalties.max_attempts,
          max_seconds_per_attempt: is_num(payload.maxSecondsPerAttempt) && payload.maxSecondsPerAttempt > 0
            ? payload.maxSecondsPerAttempt : protocol_initial_state.penalties.max_seconds_per_attempt,
          tick_rate: is_num(payload.tickRate) && payload.tickRate > 0
            ? payload.tickRate : protocol_initial_state.penalties.tick_rate,
        },
      }
    case 'PENALTY_SHOT_RESULT': {
      const penalty_team = normalize_team(payload.team)
      if (!penalty_team) return state
      const attempts = is_obj(payload.attempts) && Number.isInteger(payload.attempts[penalty_team])
        ? payload.attempts[penalty_team]
        : state.penalties.attempts[penalty_team] + 1
      const scores = is_obj(payload.score) && Number.isInteger(payload.score[penalty_team])
        ? payload.score[penalty_team]
        : state.penalties.scores[penalty_team] + (payload.status === 'scored' ? 1 : 0)
      const results = [...state.penalties.results[penalty_team]]
      if (attempts > 0 && attempts <= state.penalties.max_attempts &&
          ['scored', 'missed'].includes(payload.status)) {
        results[attempts - 1] = payload.status
      }
      return {
        ...state,
        penalties: {
          ...state.penalties,
          active: true,
          attempts: { ...state.penalties.attempts, [penalty_team]: attempts },
          scores: { ...state.penalties.scores, [penalty_team]: scores },
          results: { ...state.penalties.results, [penalty_team]: results },
          start_revision: Number.isInteger(action.server_revision)
            ? action.server_revision + 1
            : state.penalties.start_revision,
        },
      }
    }
    case 'PENALTIES_FINISHED':
      return { ...state, penalties: { ...state.penalties, active: true, completed: true, winner: normalize_team(payload.winner) } }
    case 'ERROR': {
      if (payload.team != null && (!team || team !== action.own_team)) return state
      const message = String(payload.message ?? 'Error de ejecución')
      const at_limit = payload.error_code === 'SUBSTITUTION_LIMIT_REACHED'
      return {
        ...state,
        errors: [{ code: payload.error_code ?? payload.code, message, player_id: payload.playerId }, ...state.errors].slice(0, 5),
        toast: message,
        changes_used_this_pause: at_limit && team
          ? { ...state.changes_used_this_pause, [team]: true }
          : state.changes_used_this_pause,
      }
    }
    default: return state
  }
}

function MatchView({ match_id, room_behavior_names }) {
  const [protocol_state, dispatch_protocol] = useReducer(protocol_reducer, protocol_initial_state)
  const [behavior_list, set_behavior_list] = useState([])
  const [change_open, set_change_open] = useState(false)
  const [toast, set_toast] = useState(null)
  const [submitting_changes, set_submitting_changes] = useState(false)
  const close_toast = useCallback(() => set_toast(null), [])
  const [substitution_open, set_substitution_open] = useState(false)
  const [selected_out, set_selected_out] = useState(null)
  const [selected_in, set_selected_in] = useState(null)
  const [submitting_substitution, set_submitting_substitution] = useState(false)
  const [substitution_error, set_substitution_error] = useState('')
  const own_club_id = useMemo(() => read_session()?.club_id, [])
  const own_team_ref = useRef(null)
  const pending_behavior_changes_ref = useRef(new Set())
  const state_revision_ref = useRef(null)
  const receive_protocol_message = useCallback((raw) => {
    if (raw?.type === 'connection') {
      dispatch_protocol({ type: 'connection', value: raw.value })
      return
    }
    const change_result = parse_change_result(raw)
    if (change_result) {
      const pending = pending_behavior_changes_ref.current

      if (!change_result.ok) {
        pending.clear()
        set_submitting_changes(false)
        set_toast({ type: 'error', message: change_result.message })
        return
      }

      const player_id =
        change_result.playerId ?? pending.values().next().value

      if (player_id == null || !pending.has(player_id)) return

      pending.delete(player_id)

      if (pending.size === 0) {
        set_submitting_changes(false)
        set_change_open(false)
        set_toast({
          type: 'success',
          message: 'Comportamiento actualizado para el siguiente tick',
        })
      }

      return
    }

    const message = parse_match_message(raw)
    if (message) {
      const team = normalize_team(message.payload.team)
      const is_own_team_event = team !== null && team === own_team_ref.current
      const is_substitution_error = message.event === 'ERROR' &&
        typeof message.payload.error_code === 'string' &&
        message.payload.error_code.startsWith('SUBSTITUTION_')
      if (is_own_team_event && ['SUBSTITUTION_SCHEDULED', 'SUBSTITUTION_APPLIED'].includes(message.event)) {
        set_submitting_substitution(false)
        set_substitution_error('')
      } else if (is_own_team_event && is_substitution_error) {
        set_submitting_substitution(false)
        set_substitution_error(String(message.payload.message ?? 'Error de sustitución'))
      }
      dispatch_protocol({
        type: 'message',
        message,
        own_team: own_team_ref.current,
        server_revision: state_revision_ref.current,
      })
    }
  }, [])
  const { state, error, loading, waiting_for_start, send_message,send_match_command} = useMatchState(match_id, receive_protocol_message)
  const own_team = state && own_club_id === state.home_club.club_id ? 'HOME'
    : state && own_club_id === state.away_club.club_id ? 'AWAY' : null
  useEffect(() => {
    own_team_ref.current = own_team
  }, [own_team])
  useEffect(() => {
    state_revision_ref.current = state?.revision ?? null
  }, [state?.revision])
  const [retrying_start, set_retrying_start] = useState(false)
  const [start_error, set_start_error] = useState('')
  const previous_status = useRef(null)

  useEffect(() => {
    if (previous_status.current === 'paused' && state?.status === 'in_progress') {
      dispatch_protocol({ type: 'message', message: { event: 'MATCH_RESUMED', payload: {} } })
    }
    previous_status.current = state?.status ?? null
  }, [state?.status])

  useEffect(() => {
    if (!protocol_state.toast) return undefined
    const timer = setTimeout(() => dispatch_protocol({ type: 'dismiss_toast' }), 4500)
    return () => clearTimeout(timer)
  }, [protocol_state.toast])

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
      set_behavior_list(behaviors)
    }).catch(() => {
      // El catálogo puede no incluir comportamientos privados del rival.
      // Su ausencia no debe interrumpir la transmisión del partido.
      if (!controller.signal.aborted) {
        set_behavior_names({})
        set_behavior_list([])
      }
    })
    
    return () => controller.abort()
  }, [has_state])

  function confirm_changes(changes) {
    if (
      !Array.isArray(changes) ||
      changes.length === 0 ||
      submitting_changes
    ) {
      return
    }

    const pending = new Set(changes.map(({ playerId }) => playerId))
    pending_behavior_changes_ref.current = pending
    set_submitting_changes(true)

    try {
      for (const { playerId, behaviorId } of changes) {
        const message = build_change_behavior_message(playerId, behaviorId)

        if (!send_message(message)) {
          throw new Error(
            'No se pudo enviar el cambio. Verificá la conexión.'
          )
        }
      }
    } catch (cause) {
      pending_behavior_changes_ref.current.clear()
      set_submitting_changes(false)
      set_toast({
        type: 'error',
        message: cause.message || 'No se pudieron enviar los cambios.',
      })
    }
  }

  const behavior_name = (player) => player.behavior_name?.trim() || behavior_names[player.behavior_id] || room_behavior_names?.[player.behavior_id] || 'Nombre no disponible'
  const encounter = state ? `${state.home_club.name} vs. ${state.away_club.name}` : 'Estado del partido'
  const team_coach_active = state?.coach_active === true ||
    state?.active_coach === true ||
    state?.coach_active?.[own_team] === true ||
    state?.coach_active?.[own_club_id] === true
  const roster = state?.players.filter((player) => player.club_id === own_club_id) ?? []
  const latest_applied = protocol_state.substitution_last_applied
  const modal_roster = latest_applied?.team === own_team
    ? roster.map((player) => {
      if (player.player_id === latest_applied.outPlayerId && player.on_field) {
        return { ...player, on_field: false, position: null }
      }
      if (player.player_id === latest_applied.inPlayerId && !player.on_field) {
        const outgoing_position = roster.find((item) => item.player_id === latest_applied.outPlayerId)?.position
        return { ...player, on_field: true, position: outgoing_position ?? player.position }
      }
      return player
    })
    : roster
  const starters = modal_roster.filter((player) => player.on_field)
  const substitutes = modal_roster.filter((player) => !player.on_field)
  const pending_substitution = own_team ? protocol_state.pending_substitutions[own_team] : null
  const changes_used_this_pause = own_team ? protocol_state.changes_used_this_pause[own_team] : false
  const open_substitutions = () => {
    set_selected_out(null)
    set_selected_in(null)
    set_substitution_error('')
    set_substitution_open(true)
  }
  const close_substitutions = () => set_substitution_open(false)
  const confirm_substitution = () => {
    if (!selected_out || !selected_in || !own_team || submitting_substitution ||
        changes_used_this_pause || pending_substitution) return
    set_submitting_substitution(true)
    set_substitution_error('')
    try {
      send_match_command({ type: 'SUBSTITUTE_PLAYER', outPlayerId: selected_out, inPlayerId: selected_in })
    } catch (cause) {
      set_submitting_substitution(false)
      set_substitution_error(cause.message || 'No se pudo enviar la sustitución.')
    }
  }
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
          <LiveMatchControls
            status={state.status}
            visible={Boolean(own_team) && !protocol_state.penalties.active}
            disabled={team_coach_active}
            onOpen={open_substitutions}
          />
          <PenaltyShootout
            penalties={protocol_state.penalties}
            home_name={state.home_club.name}
            away_name={state.away_club.name}
            revision={state.revision}
          />
          <div className="match-pitch-stage">
            {/* current_time is frozen during a pause, so the key only changes when a new pause starts. */}
            {state.status === 'paused' && <PauseBanner key={`${state.phase}-${state.current_time}`} phase={state.phase} pause_duration={state.pause_duration} pause_remaining={state.pause_remaining} />}
            <MatchPitch
              state={state}
              protocol_state={protocol_state}
              penalties_active={protocol_state.penalties.active}
            />
          </div>
          <div className="match-pitch-footer"><Link to="/home">← Volver al menú</Link><span>Restante: <time>{time(state.remaining_time)}</time></span></div>
          <div className="match-change-behavior">
            {state.status !== 'finished' && (
              <button
                type="button"
                className="home-action"
                disabled={behavior_list.length === 0 || submitting_changes}
                onClick={() => set_change_open(true)}
              >
                Cambiar comportamiento
              </button>
            )}
          </div>
          {change_open && (
            <ChangeBehaviorModal
              starters={get_my_starters(state, read_session()?.club_id)}
              behaviors={behavior_list}
              submitting={submitting_changes}
              on_confirm={confirm_changes}
              on_close={() => set_change_open(false)}
            />
          )}

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
        {substitution_open && own_team && (
          <SubstitutionModal
            team_name={own_team === 'HOME' ? state.home_club.name : state.away_club.name}
            starters={starters}
            substitutes={substitutes}
            pending={pending_substitution}
            used_this_pause={changes_used_this_pause}
            selected_out={selected_out}
            selected_in={selected_in}
            submitting={submitting_substitution}
            error={substitution_error}
            on_select_out={(player_id) => set_selected_out((current) => current === player_id ? null : player_id)}
            on_select_in={(player_id) => set_selected_in((current) => current === player_id ? null : player_id)}
            on_submit={confirm_substitution}
            on_close={close_substitutions}
          />
        )}
      </>}
      {protocol_state.toast && (
        <div className="match-toast" role="status" aria-live="polite">{protocol_state.toast}</div>
      )}
      </main>
      {toast && <Toast type={toast.type} message={toast.message} on_close={close_toast} />}
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
