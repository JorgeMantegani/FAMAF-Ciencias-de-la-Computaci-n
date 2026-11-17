import { useEffect, useState } from 'react'
import { API_URL } from '../api/client'
import { clear_session, read_session } from '../auth/session'

const WS_URL = `${API_URL.replace(/^http/, 'ws')}/ws/friendly-rooms/public`   // http -> ws, https -> wss
const CLOSE_UNAUTHORIZED = 4401
const MAX_DELAY_MS = 15000

// Avisa a la pantalla que la sesión ya no sirve, para que lleve al login.
function notify_unauthorized() {
  window.dispatchEvent(new Event('futbot:unauthorized'))
}

// Borra la sesión solo si sigue siendo la que falló: así no se pisa una sesión nueva
// abierta en otra pestaña (mismo criterio que client.js).
function expire_session(failed) {
  if (read_session()?.refresh_token === failed?.refresh_token) clear_session()
  notify_unauthorized()
}

// El servidor guarda en UTC; si la fecha llega sin zona horaria, se le agrega "Z"
// (si no, el navegador la interpretaría como hora local).
function parse_utc(value) {
  if (typeof value !== 'string') return null
  const has_zone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value)
  const date = new Date(has_zone ? value : `${value}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

// Deja de cada sala solo lo que usa la pantalla
function normalize_room(raw) {
  return {
    id: raw.roomId ?? raw.room_id,
    status: raw.status,
    home_club_id: raw.homeClub ?? raw.home_club,
    home_club_name: raw.homeClubName ?? raw.home_club_name ?? '',
    created_at: parse_utc(raw.createdAt ?? raw.created_at),
  }
}

// Mantiene abierto el canal de amistosos públicos y devuelve el último listado recibido.
// connection: 'connecting' (todavía no llegó nada), 'online' o 'offline' (se cortó y reintenta).
export function usePublicFriendlySocket() {
  const [rooms, set_rooms] = useState(null)             // null hasta recibir el primer listado
  const [connection, set_connection] = useState('connecting')

  useEffect(() => {
    let timer
    let failures = 0
    let socket
    let closed = false

    function connect() {
      const session = read_session()
      if (!session) {                                   // la sesión venció o se cerró en otra pestaña
        closed = true                                   // no hay nada que reintentar
        set_connection('offline')
        notify_unauthorized()                           // la pantalla lleva al login
        return
      }
      socket = new WebSocket(WS_URL)

      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'auth', token: session.access_token }))
      }

      socket.onmessage = (event) => {
        let message
        try {
          message = JSON.parse(event.data)
        } catch {
          return
        }
        if (message.type !== 'rooms' || !Array.isArray(message.rooms)) return
        failures = 0
        set_connection('online')
        set_rooms(message.rooms.map(normalize_room))
      }

      socket.onclose = (event) => {
        if (closed) return                              // cierre propio al salir de la pantalla
        set_connection('offline')
        if (event.code === CLOSE_UNAUTHORIZED) {        // el servidor rechazó el token
          closed = true                                 // reintentar con el mismo token no sirve
          expire_session(session)                       // se borra solo si sigue siendo la sesión que falló
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
      socket?.close()
    }
  }, [])

  return { rooms, connection }
}