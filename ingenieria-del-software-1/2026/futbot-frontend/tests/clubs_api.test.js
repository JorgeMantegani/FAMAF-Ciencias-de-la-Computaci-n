import { expect, it, vi } from 'vitest'
import { request } from '../src/api/client'
import { get_club_ranking } from '../src/api/clubs'

vi.mock('../src/api/client', () => ({ request: vi.fn() }))

it('usa el endpoint paginado y propaga la señal de cancelación al cliente autenticado', async () => {
  const signal = new AbortController().signal
  request.mockResolvedValue({ items: [] })
  expect(await get_club_ranking({ page: 2, size: 20, signal })).toEqual({ items: [] })
  expect(request).toHaveBeenCalledWith('/api/clubs/ranking?page=2&size=20', { signal })
})
