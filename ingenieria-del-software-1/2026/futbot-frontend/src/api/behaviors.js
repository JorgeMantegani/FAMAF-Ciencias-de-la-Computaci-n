import { API_URL, request } from './client'

export const get_behaviors = (options = {}) => request('/api/behaviors', options)

export const delete_behavior = (behavior_id, options = {}) =>
    request(`/api/behaviors/${behavior_id}`, { method: 'DELETE', ...options })
export const create_behavior = (data, options = {}) => 
  request('/api/behaviors', 
    { ...options, 
      method: 'POST', 
      body: JSON.stringify(data) 
    }
  )
export const get_behavior = (behavior_id, options = {}) =>
  request(`/api/behaviors/${encodeURIComponent(behavior_id)}`, options)

export const update_behavior = (behavior_id, data, options = {}) =>
  request(`/api/behaviors/${encodeURIComponent(behavior_id)}`,
    { ...options,
      method: 'PUT',
      body: JSON.stringify(data)
    }
  )

export function create_simulation_ticket(player_id, behavior_id, options = {}) {
  return request(`/api/behaviors/simulate`,
    { ...options,
      method: 'POST',
      body: JSON.stringify({ player_id, behavior_id })
    }
  )
}

export function connect_to_simulation_ticket(ticket) {
  const base = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws')
  // /ws/simulate?ticket=<ticket>
  const ws = new WebSocket(`${base.replace(/\/$/, '')}/ws/simulate?ticket=${encodeURIComponent(ticket)}`)
  return ws
}
