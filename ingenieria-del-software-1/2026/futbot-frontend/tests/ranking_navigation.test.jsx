import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../src/App'
import { get_club_ranking } from '../src/api/clubs'
import { read_session } from '../src/auth/session'

vi.mock('../src/api/clubs', () => ({ get_club_ranking: vi.fn() }))
vi.mock('../src/auth/session', async (original) => ({
  ...await original(), read_session: vi.fn(),
}))
vi.mock('../src/pages/behavior_page', () => ({
  default: () => <h1>Comportamientos</h1>,
}))

beforeEach(() => {
  vi.resetAllMocks()
  read_session.mockReturnValue({ club_id: 'own', access_token: 'token' })
  get_club_ranking.mockResolvedValue({
    items: [{ position: 1, clubId: 'rival', clubName: 'Rival FC', avatar: null, rankingPoints: 50 }],
    page: 1, size: 20, totalPages: 1, totalClubs: 2,
    userClubRanking: { position: 2, rankingPoints: 10 },
  })
})

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

it.each(['/ranking', '/behaviors'])('abre el ranking desde %s con el router real', async (path) => {
  const user = userEvent.setup()
  window.history.replaceState(null, '', path)
  render(<App />)

  const link = screen.getByRole('link', { name: 'Ranking de clubes' })
  expect(link).toHaveAttribute('href', '/ranking')
  if (path !== '/ranking') {
    expect(get_club_ranking).not.toHaveBeenCalled()
    await user.click(link)
  }

  expect(await screen.findByRole('table')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/ranking')
  await user.click(screen.getByRole('button', { name: 'Ver perfil de Rival FC' }))
  const dialog = screen.getByRole('dialog', { name: 'Perfil público de Rival FC' })
  expect(within(dialog).getByText('50')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/ranking')
  await user.click(within(dialog).getByRole('button', { name: 'Cerrar perfil' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('table')).toBeInTheDocument()
})
