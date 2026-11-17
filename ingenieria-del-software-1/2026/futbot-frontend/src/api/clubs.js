import { request } from './client'

export function get_club_ranking({ page = 1, size = 20, signal } = {}) {
  return request(`/api/clubs/ranking?${new URLSearchParams({ page, size })}`, { signal })
}
