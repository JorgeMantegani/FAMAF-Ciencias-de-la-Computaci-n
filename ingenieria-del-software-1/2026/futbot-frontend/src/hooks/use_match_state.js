import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { connect_match_state } from '../api/matches'
import { clear_session, read_session } from '../auth/session'

const terminal_errors = {
  403: 'No tenés acceso a este partido.',
  404: 'El partido no existe.',
  422: 'El ID del partido no es válido.',
}

function valid_state(state, match_id) {
  const point = (value) => value && Number.isFinite(value.x) && Number.isFinite(value.y)
  return state?.match_id === match_id && Number.isInteger(state.revision) && state.revision > 0 &&
    ['in_progress', 'paused', 'finished'].includes(state.status) &&
    typeof state.home_club?.name === 'string' && typeof state.away_club?.name === 'string' &&
    Number.isFinite(state.score?.home) && Number.isFinite(state.score?.away) &&
    Number.isFinite(state.current_time) && Number.isFinite(state.remaining_time) && point(state.ball) &&
    Array.isArray(state.players) && state.players.every((player) => player && typeof player.name === 'string' && (!player.on_field || point(player.position))) &&
    Array.isArray(state.actions) && state.actions.every((action) => action && typeof action.type === 'string')
}

export default function useMatchState(match_id, on_protocol_message) {
  const navigate = useNavigate()
  const [view, set_view] = useState({ state: null, error: '', loading: true })
  const protocol_message_ref = useRef(on_protocol_message)

  useEffect(() => {
    protocol_message_ref.current = on_protocol_message
  }, [on_protocol_message])

  useEffect(() => {
    let disposed = false
    let stopped = false
    let socket
    let reconnect_timer
    let watchdog
    let expiry_timer
    let latest = null
    let attempts = 0
    let connected_session

    const disconnect = () => {
      clearTimeout(watchdog)
      if (socket) {
        socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null
        socket.close()
        socket = null
      }
    }
    const unauthorized = () => {
      stopped = true
      clearTimeout(reconnect_timer)
      disconnect()
      navigate('/login', { replace: true })
    }
    const reject_session = () => {
      if (read_session()?.refresh_token === connected_session?.refresh_token) clear_session()
      unauthorized()
    }
    const check_session = () => {
      clearTimeout(expiry_timer)
      const current = read_session()
      if (!current) { unauthorized(); return }
      // No conservar una conexión del usuario anterior al cambiar de cuenta.
      if (connected_session && current.access_token !== connected_session.access_token) {
        clearTimeout(reconnect_timer)
        disconnect()
        latest = null
        stopped = false
        set_view({ state: null, error: '', loading: true })
        connect()
      }
      expiry_timer = setTimeout(check_session, Math.min(current.expires_at * 1000 - Date.now(), 2147483647))
    }
    const storage_changed = (event) => {
      if (event.key === 'futbot.session' || event.key === null) check_session()
    }
    const retry = () => {
      if (disposed || stopped) return
      protocol_message_ref.current?.({ type: 'connection', value: 'reconnecting' })
      disconnect()
      clearTimeout(reconnect_timer)
      set_view({ state: latest, loading: false, error: 'No se pudo actualizar el partido. Reintentando automáticamente…' })
      reconnect_timer = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 10000))
    }
    const arm_watchdog = (delay) => {
      clearTimeout(watchdog)
      watchdog = setTimeout(retry, delay)
    }
    function connect() {
      if (disposed || stopped) return
      connected_session = read_session()
      if (!connected_session) { unauthorized(); return }
      try {
        const current = connect_match_state(match_id)
        socket = current
        arm_watchdog(10000)
        current.onopen = () => {
          if (socket !== current || disposed) return
          protocol_message_ref.current?.({ type: 'connection', value: 'open' })
          current.send(JSON.stringify({ type: 'auth', token: connected_session.access_token }))
        }
        current.onmessage = (event) => {
          if (socket !== current || disposed || stopped) return
          try {
            const message = JSON.parse(event.data)
            arm_watchdog(45000)
            if (message.type === 'ping') {
              current.send(JSON.stringify({ type: 'pong' }))
              return
            }
            if (message.type === 'error') {
              if (message.status === 401) { reject_session(); return }
              if (terminal_errors[message.status]) {
                stopped = true
                latest = null
                disconnect()
                set_view({ state: null, loading: false, error: terminal_errors[message.status] })
                return
              }
              if (message.status === 409) {
                set_view({ state: latest, loading: false, waiting_for_start: !latest, error: 'Esperando el estado inicial del partido. Se actualizará automáticamente.' })
                return
              }
              retry()
              return
            }
            // Los snapshots siguen siendo el formato principal. Los mensajes
            // event/payload se reenvían a la página para procesarlos allí.
            if (message.type !== 'state') {
              protocol_message_ref.current?.(event.data)
              return
            }
            if (!valid_state(message.state, match_id)) throw new Error('Estado inválido')
            if (!latest || message.state.revision >= latest.revision) latest = message.state
            attempts = 0
            set_view({ state: latest, loading: false, error: '' })
            if (latest.status === 'finished') {
              stopped = true
              disconnect()
            }
          } catch {
            retry()
          }
        }
        current.onerror = retry
        current.onclose = (event) => {
          if (event.code === 4401) { reject_session(); return }
          const status = { 4403: 403, 4404: 404, 4422: 422 }[event.code]
          if (status) {
            stopped = true
            disconnect()
            set_view({ state: null, loading: false, error: terminal_errors[status] })
          } else retry()
        }
      } catch {
        retry()
      }
    }

    check_session()
    window.addEventListener('futbot:unauthorized', unauthorized)
    window.addEventListener('storage', storage_changed)
    window.addEventListener('focus', check_session)
    document.addEventListener('visibilitychange', check_session)
    connect()
    return () => {
      disposed = true
      disconnect()
      clearTimeout(reconnect_timer)
      clearTimeout(expiry_timer)
      window.removeEventListener('futbot:unauthorized', unauthorized)
      window.removeEventListener('storage', storage_changed)
      window.removeEventListener('focus', check_session)
      document.removeEventListener('visibilitychange', check_session)
    }
  }, [match_id, navigate])

  return view
}
