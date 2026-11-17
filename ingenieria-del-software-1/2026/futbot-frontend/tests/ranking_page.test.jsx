import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import RankingPage from '../src/pages/ranking_page'
import { get_club_ranking } from '../src/api/clubs'
import { read_session } from '../src/auth/session'

vi.mock('../src/api/clubs', () => ({ get_club_ranking: vi.fn() }))
vi.mock('../src/auth/session', () => ({ read_session: vi.fn() }))

const clubs = [
  { position: 1, clubId: 'alpha', clubName: 'Alpha', avatar: '1', rankingPoints: 50 },
  { position: 2, clubId: 'beta', clubName: 'Beta', avatar: '/avatars/2.jpg', rankingPoints: 40 },
  { position: 3, clubId: 'own', clubName: 'Mi club', avatar: null, rankingPoints: 28 },
]
const firstPage = {
  items: clubs, page: 1, size: 20, totalPages: 2, totalClubs: 21,
  userClubRanking: { position: 3, rankingPoints: 28 },
}
const secondPage = {
  ...firstPage, page: 2,
  items: [{ position: 21, clubId: 'last', clubName: 'Último', avatar: '3', rankingPoints: 0 }],
}

function Location() {
  return <output aria-label="Ruta actual">{useLocation().pathname}</output>
}
function mount() {
  return render(<MemoryRouter initialEntries={['/ranking']}>
    <Location />
    <Routes>
      <Route path="/ranking" element={<RankingPage />} />
      <Route path="/login" element={<h1>Iniciar sesión</h1>} />
    </Routes>
  </MemoryRouter>)
}

beforeEach(() => {
  vi.resetAllMocks()
  read_session.mockReturnValue({ club_id: 'own', access_token: 'token' })
  get_club_ranking.mockResolvedValue(firstPage)
})

describe('Ranking de clubes', () => {
  it('muestra skeleton mientras espera la respuesta', async () => {
    let resolve
    get_club_ranking.mockReturnValue(new Promise((done) => { resolve = done }))
    mount()
    expect(screen.getByRole('status', { name: 'Cargando ranking' })).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    await act(async () => resolve(firstPage))
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  it('respeta el orden del backend, muestra columnas y destaca podio y club propio', async () => {
    mount()
    const table = await screen.findByRole('table')
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Posición', 'Club', 'Puntos'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((row) => within(row).getByRole('button').getAttribute('aria-label')))
      .toEqual(['Ver perfil de Alpha', 'Ver perfil de Beta', 'Ver perfil de Mi club'])
    expect(rows[2]).toHaveClass('ranking-own-club')
    expect(rows[0]).not.toHaveClass('ranking-own-club')
    for (const position of [1, 2, 3]) {
      expect(within(rows[position - 1]).getByRole('img', { name: `Medalla del puesto ${position}` })).toBeInTheDocument()
      expect(rows[position - 1]).toHaveClass(`ranking-top-${position}`)
    }
    expect(within(rows[0]).getByText('50')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Escudo de Alpha' })).toHaveAttribute('src', '/avatars/1.jpg')
    expect(screen.getByText('Tu club')).toBeInTheDocument()
    expect(get_club_ranking).toHaveBeenCalledWith({ page: 1, size: 20, signal: expect.any(AbortSignal) })
  })

  it.each(['nombre', 'avatar'])('abre el perfil al hacer clic en %s sin navegar y devuelve el foco', async (target) => {
    const user = userEvent.setup()
    mount()
    const button = await screen.findByRole('button', { name: 'Ver perfil de Alpha' })
    await user.click(target === 'nombre' ? within(button).getByText('Alpha') : within(button).getByRole('img'))
    const dialog = screen.getByRole('dialog', { name: 'Perfil público de Alpha' })
    expect(within(dialog).getByText('50')).toBeInTheDocument()
    expect(screen.getByLabelText('Ruta actual')).toHaveTextContent('/ranking')
    expect(within(dialog).getByRole('button', { name: 'Cerrar perfil' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(button).toHaveFocus()
  })

  it('pagina en ambos sentidos y conserva la posición global del usuario', async () => {
    const user = userEvent.setup()
    get_club_ranking.mockImplementation(({ page }) => Promise.resolve(page === 1 ? firstPage : secondPage))
    mount()
    await screen.findByRole('table')
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByRole('button', { name: 'Ver perfil de Último' })).toBeInTheDocument()
    expect(screen.getByText('21', { selector: '.ranking-position' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled()
    expect(screen.getByText('#3')).toBeInTheDocument()
    expect(screen.queryByText('Tu club')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Anterior' }))
    expect(await screen.findByRole('button', { name: 'Ver perfil de Alpha' })).toBeInTheDocument()
    expect(get_club_ranking.mock.calls.map(([args]) => args.page)).toEqual([1, 2, 1])
  })

  it('permite reintentar tras un error', async () => {
    const user = userEvent.setup()
    get_club_ranking.mockRejectedValueOnce(new Error('network'))
    mount()
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el ranking')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(get_club_ranking).toHaveBeenCalledTimes(2)
  })

  it('muestra una página vacía y permite regresar', async () => {
    const user = userEvent.setup()
    get_club_ranking.mockResolvedValueOnce(firstPage).mockResolvedValueOnce({ ...secondPage, items: [] })
    mount()
    await screen.findByRole('table')
    await user.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByText('No hay clubes en esta página.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeEnabled()
  })

  it('cancela la petición al desmontar', () => {
    get_club_ranking.mockReturnValue(new Promise(() => {}))
    const view = mount()
    const signal = get_club_ranking.mock.calls[0][0].signal
    view.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('redirige al login sin sesión y no consulta el ranking', async () => {
    read_session.mockReturnValue(null)
    mount()
    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument()
    expect(get_club_ranking).not.toHaveBeenCalled()
  })

  it('redirige al login si el servidor devuelve 401', async () => {
    get_club_ranking.mockRejectedValue({ status: 401 })
    mount()
    await waitFor(() => expect(screen.getByLabelText('Ruta actual')).toHaveTextContent('/login'))
  })
})
