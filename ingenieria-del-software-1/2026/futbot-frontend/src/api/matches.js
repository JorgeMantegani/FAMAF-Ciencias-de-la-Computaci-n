import { API_URL, request } from './client'

export function retry_match_start(match_id) {
  return request(`/matches/${encodeURIComponent(match_id)}/start`, { method: 'POST' })
}

export function connect_match_state(match_id) {
  const base = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws')
  return new WebSocket(`${base.replace(/\/$/, '')}/api/matches/${encodeURIComponent(match_id)}/ws`)
}
