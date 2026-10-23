import { request } from './client'

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
