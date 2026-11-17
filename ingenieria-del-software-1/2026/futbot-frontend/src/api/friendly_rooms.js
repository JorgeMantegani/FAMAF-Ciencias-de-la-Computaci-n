import { API_URL, request } from './client'

export const ROOM_STATUS = {
  WAITING_GUEST: 'waitingGuest',
  READY_TO_START: 'readyToStart',
  IN_PROGRESS: 'inProgress',
  FINISHED: 'finished',
  CANCELLED: 'cancelled',
}

export function get_friendly_room(room_id) {
  return request(`/api/friendly/rooms/${encodeURIComponent(room_id)}`)
}

export function start_friendly_match(room_id) {
  return request(`/api/friendly/rooms/${encodeURIComponent(room_id)}/start`, {
    method: 'POST',
  })
}

export function connect_friendly_room_ws(room_id, club_id) {
  const base = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws')
  return new WebSocket(
    `${base.replace(/\/$/, '')}/ws/friendly/${encodeURIComponent(room_id)}?club_id=${encodeURIComponent(club_id)}`
  )
}