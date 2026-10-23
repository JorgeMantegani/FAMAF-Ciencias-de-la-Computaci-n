import { clear_session, read_session } from '../auth/session'

// Cliente HTTP del backend de FutBot.
export const API_URL = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, detail, error_code) {
    const message = Array.isArray(detail)
      ? detail
          .map((item) => {
            const field = Array.isArray(item.loc)
              ? item.loc.join('.')
              : 'campo'
            return `${field}: ${item.msg ?? 'Dato inválido'}`
          })
          .join(' | ')
      : typeof detail === 'string'
        ? detail
        : 'Error desconocido'

    super(message)

    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.error_code = error_code
  }
}

let signing_out = false

function with_session_lock(operation) {
  return navigator.locks
    ? navigator.locks.request('futbot.session', operation)
    : operation()
}

function expire_session(session) {
  if (read_session()?.refresh_token === session?.refresh_token) {
    clear_session()
    window.dispatchEvent(new Event('futbot:unauthorized'))
  }
}

// Lee la respuesta sin perder el estado HTTP si el backend no devuelve JSON.
async function response_body(response) {
  let body = null

  if (response.status !== 204) {
    const text = await response.text()

    if (text) {
      try {
        body = JSON.parse(text)
      } catch {
        body = { detail: text }
      }
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.detail ?? `Error HTTP ${response.status}`,
      body?.error_code
    )
  }

  return body
}

export async function request(path, options = {}) {
  const { authenticated = true, ...fetch_options } = options
  const session = authenticated ? read_session() : null

  const headers = new Headers(fetch_options.headers)

  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (session) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...fetch_options,
    headers,
  })

  if (response.status === 401 && session && !signing_out) {
    expire_session(session)
  }

  if (authenticated && signing_out) {
    throw new DOMException('Sesión cerrándose', 'AbortError')
  }

  return response_body(response)
}

export async function logout() {
  signing_out = true

  try {
    await with_session_lock(async () => {
      const session = read_session()
      if (!session) return

      const response = await fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
      })

      if (response.status !== 401) {
        await response_body(response)
      }

      expire_session(session)
    })
  } finally {
    signing_out = false
  }
}

export function get_health() {
  return request('/api/health', { authenticated: false })
}

export function login({ email, password }) {
  return request('/api/auth/login', {
    authenticated: false,
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function get_current_user(options = {}) {
  return request('/api/auth/me', options)
}

// Admite respuestas como [...] o { players: [...] }.
function as_list(body, key) {
  if (Array.isArray(body)) return body
  return Array.isArray(body?.[key]) ? body[key] : []
}

export async function list_players(options = {}) {
  const body = await request('/api/players', options)
  return as_list(body, 'players')
}

export async function list_behaviors(options = {}) {
  const body = await request('/api/behaviors', options)
  return as_list(body, 'behaviors')
}

// Convierte el equipo del frontend al formato usado por el endpoint /join.
export function join_friendly_room({
  room_id,
  code,
  starters,
  substitutes,
}) {
  const to_payload = ({ player_id, behavior_id }) => ({
    playerId: String(player_id),
    behaviorId: String(behavior_id),
  })

  return request(
    `/api/friendly/rooms/${encodeURIComponent(room_id)}/join`,
    {
      method: 'POST',
      body: JSON.stringify({
        code,
        starters: starters.map(to_payload),
        substitutes: substitutes.map(to_payload),
      }),
    }
  )
}