import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import Home from '../src/pages/Home'
import { get_current_user } from '../src/api/client'
import { createPlayer } from '../src/api/players'
import { save_session } from '../src/auth/session'

vi.mock('../src/api/client', () => ({ get_current_user: vi.fn(), logout: vi.fn() }))
vi.mock('../src/api/players.js', () => ({ createPlayer: vi.fn() }))

function Destination() {
  return <p>Destino: {useLocation().pathname}</p>
}

beforeEach(() => {
  vi.resetAllMocks()
  save_session({ access_token: 'token', refresh_token: 'refresh', club_id: 'club', expires_at: Date.now() / 1000 + 3600 })
  get_current_user.mockResolvedValue({ club_id: 'club' })
  createPlayer.mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
})

async function mount() {
  render(<MemoryRouter initialEntries={['/home']}><Routes>
    <Route path="/home" element={<Home />} />
    <Route path="/partidos/:match_id" element={<Destination />} />
    <Route path="/behaviors" element={<Destination />} />
  </Routes></MemoryRouter>)
  await screen.findByRole('heading', { name: 'Menú principal' })
  return userEvent.setup()
}

it('conserva las dos opciones del menú y permite entrar a comportamientos', async () => {
  const user = await mount()
  expect(screen.getByRole('article', { name: 'Estado del partido' })).toBeInTheDocument()
  expect(screen.getByRole('article', { name: 'Comportamientos' })).toHaveAccessibleDescription(
    'Define reglas, bloques y comportamientos para cada jugador antes de enviarlos al campo.',
  )
  await user.click(screen.getByRole('link', { name: 'VER COMPORTAMIENTOS' }))
  expect(screen.getByText('Destino: /behaviors')).toBeInTheDocument()
})

it('abre el partido con el ID recortado y codificado', async () => {
  const user = await mount()
  await user.type(screen.getByLabelText('ID del partido'), ' partido/1 ')
  await user.click(screen.getByRole('button', { name: 'Ver partido' }))
  expect(screen.getByText('Destino: /partidos/partido%2F1')).toBeInTheDocument()
})

it('no navega cuando el ID contiene solo espacios', async () => {
  const user = await mount()
  await user.type(screen.getByLabelText('ID del partido'), '   ')
  await user.click(screen.getByRole('button', { name: 'Ver partido' }))
  expect(screen.getByRole('heading', { name: 'Menú principal' })).toBeInTheDocument()
})

it('abre el modal de creación de jugador desde la tarjeta de Home', async () => {
  const user = await mount()
  await user.click(screen.getByRole('button', { name: 'CREAR JUGADOR' }))
  expect(screen.getByRole('dialog', { name: 'Crear Jugador' })).toBeInTheDocument()
  expect(screen.getByLabelText('Nombre')).toBeInTheDocument()
})
