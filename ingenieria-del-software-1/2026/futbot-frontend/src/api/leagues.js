import { request } from './client'
import { ROOM_STATUS } from './friendly_rooms'
import { read_session } from "../auth/session";

export const OPEN_LEAGUE_STATUSES = [ROOM_STATUS.WAITING_GUEST, ROOM_STATUS.READY_TO_START]

export const LEAGUE_STATUS_LABELS = {
  [ROOM_STATUS.WAITING_GUEST]: 'Esperando clubes',
  [ROOM_STATUS.READY_TO_START]: 'Lista para empezar',
  [ROOM_STATUS.IN_PROGRESS]: 'En juego',
  [ROOM_STATUS.FINISHED]: 'Finalizada',
  [ROOM_STATUS.CANCELLED]: 'Cancelada',
}

const league_path = (league_id) => `/api/leagues/${encodeURIComponent(league_id)}`

const to_selection = ({ playerId, behaviorId }) => ({
  playerId: String(playerId),
  behaviorId: String(behaviorId),
})

export function get_league(league_id, options = {}) {
  return request(league_path(league_id), options)
}

export function find_league_by_code(code, options = {}) {
  return request(`/api/leagues/by-code/${encodeURIComponent(code)}`, options)
}

export function join_league(league_id, { starters, substitutes, password }) {
  return request(`${league_path(league_id)}/join`, {
    method: 'POST',
    body: JSON.stringify({
      titulares: starters.map(to_selection),
      suplentes: substitutes.map(to_selection),
      ...(password ? { password } : {}),
    }),
  })
}

export const free_spots = (league) => Math.max(league.maxClubs - league.enrolledClubs, 0)

export const is_league_full = (league) => league.enrolledClubs >= league.maxClubs

export function apply_league_list(league, listed) {
  const live = listed.find(({ id }) => id === league?.leagueId)
  if (!live) return league
  return {
    ...league,
    enrolledClubs: live.participants_count,
    status:
      live.started && OPEN_LEAGUE_STATUSES.includes(league.status)
        ? ROOM_STATUS.IN_PROGRESS
        : league.status,
  }
}

// Convierte un jugador al formato de selección de escuadra.
function to_squad_selection(player) {
  return {
    player_id: String(player.playerId),
    behavior_id: String(player.behaviorId),
  };
}

export async function createLeague({
  name,
  is_private,
  has_penalty_shootout,
  password,
  min_clubs,
  max_clubs,
  match_duration,
  starters,
  substitutes,
}) {
  const session = read_session();

  if (!session) {
    throw new Error("Tu sesión venció. Iniciá sesión de nuevo.");
  }
  const req = {
    name: name.trim(),
    is_private: is_private === true,
    has_penalty_shootout: has_penalty_shootout === true,
    min_clubs: Number(min_clubs),
    max_clubs: Number(max_clubs),
    match_duration: Number(match_duration),
    starters: starters.map(to_squad_selection),
    substitutes: substitutes.map(to_squad_selection),
  };

  // Si es privada, agrega contraseña
  if (is_private === true) {
    req.password = String(password);
  }

  return request("/api/leagues", {
    method: "POST",
    headers: { Authorization: `Bearer ${session.access_token}` },
    body: JSON.stringify(req),
  });
}
export function getLeagueStandings(leagueId, { signal } = {}) {
  return request(
    `/api/leagues/${encodeURIComponent(leagueId)}/standings`,
    { signal }
  );
}

export function update_league_lineup(league_id, { starters, substitutes }) {
  return request(`${league_path(league_id)}/lineup`, {
    method: 'PUT',
    body: JSON.stringify({
      starters: starters.map(String),
      substitutes: substitutes.map(String),
    }),
  })
}