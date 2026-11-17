import { useEffect, useRef, useState } from 'react'
import { API_URL } from '../api/client'
import { clear_session, read_session } from '../auth/session'

const WS_URL = `${API_URL.replace(/^http/, 'ws')}/ws/leagues`   // http -> ws, https -> wss
const CLOSE_UNAUTHORIZED = 4401
const MAX_DELAY_MS = 15000

function notify_unauthorized() {
  window.dispatchEvent(new Event('futbot:unauthorized'))
}

function expire_session(failed) {
  if(read_session()?.refresh_token === failed?.refresh_token) clear_session()
    notify_unauthorized()
}

// Deja de cada liga solo lo que usa la pantalla
function normalize_league(raw) {
  return {
    id: raw.id,
    name: raw.name,
    participants_count: raw.participantsCount ?? raw.participants_count ?? 0,
    started: Boolean(raw.started),
  }
}

// Mantiene abierto el canal de ligas y devuelve el último listado recibido.
// - query: filtro por nombre; cada cambio se envía por el canal.
// - on_leagues(loaded, name): se llama cada vez que llega un listado.
// connection: 'connecting' (todavía no llegó nada), 'online' o 'offline' (se cortó y reintenta).
export function useLeaguesSocket(query, on_leagues) {
  const [data, set_data] = useState(null)             // { name, leagues } del último mensaje
  const [connection, set_connection] = useState('connecting')
  const socket_ref = useRef(null)
  const query_ref = useRef(query)
  const callback_ref = useRef(on_leagues)

  useEffect(() => {
    callback_ref.current = on_leagues
  }, [on_leagues])

  // Cada búsqueda nueva se envía por el canal abierto
  useEffect(() => {
    query_ref.current = query
    const socket = socket_ref.current
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'search', name: query }))
    }
  }, [query])

  useEffect(() => {
    let timer
    let failures = 0
    let closed = false

    function connect() {
      const session = read_session()
      if (!session) {
        closed = true
        set_connection('offline')
        notify_unauthorized()
        return
      }
      const socket = new WebSocket(WS_URL)
      socket_ref.current = socket

      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'auth', token: session.access_token }))
        if (query_ref.current) {                      // tras reconectar, vuelve a pedir la búsqueda activa
          socket.send(JSON.stringify({ type: 'search', name: query_ref.current }))
        }
      }

      socket.onmessage = (event) => {
        let message
        try {
          message = JSON.parse(event.data)
        } catch {
          return
        }
        if (message.type !== 'leagues' || !Array.isArray(message.leagues)) return
        const leagues = message.leagues.map(normalize_league)
        const name = typeof message.name === 'string' ? message.name : ''
        failures = 0
        set_connection('online')
        set_data({ name, leagues })
        callback_ref.current?.(leagues, name)
      }

      socket.onclose = (event) => {
        if (socket_ref.current === socket) socket_ref.current = null
        if (closed) return                            // cierre propio al salir de la pantalla
        set_connection('offline')
        if (event.code === CLOSE_UNAUTHORIZED) {      // el token no sirve: mismo trato que un 401 del HTTP
          closed = true
          expire_session(session)
          return
        }
        timer = setTimeout(connect, Math.min(1000 * 2 ** failures, MAX_DELAY_MS))
        failures += 1
      }
    }

    connect()
    return () => {
      closed = true
      clearTimeout(timer)
      socket_ref.current?.close()
    }
  }, [])

  return { data, connection }
}