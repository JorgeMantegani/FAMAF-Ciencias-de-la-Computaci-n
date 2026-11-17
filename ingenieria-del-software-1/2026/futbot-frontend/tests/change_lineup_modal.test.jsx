import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import ChangeLineupModal from '../src/components/change_lineup_modal.jsx'
import * as leaguesApi from '../src/api/leagues'

// Mock del servicio API de ligas
vi.mock('../src/api/leagues', () => ({
  update_league_lineup: vi.fn(),
}))

describe('ChangeLineupModal Component', () => {
  const mockSquad = [
    { player_id: 'p1', name: 'Jugador 1', role: 'starter' },
    { player_id: 'p2', name: 'Jugador 2', role: 'starter' },
    { player_id: 'p3', name: 'Jugador 3', role: 'starter' },
    { player_id: 'p4', name: 'Jugador 4', role: 'substitute' },
    { player_id: 'p5', name: 'Jugador 5', role: 'substitute' },
    { player_id: 'p6', name: 'Jugador 6', role: 'substitute' },
  ]

  const defaultProps = {
    league_id: 'league-123',
    squad: mockSquad,
    onClose: vi.fn(),
    onSuccess: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })
  it('Debe renderizar la alineación inicial con 3 titulares y 3 suplentes', () => {
    render(<ChangeLineupModal {...defaultProps} />)

    expect(screen.getByRole('heading', { name: /cambiar alineación/i })).toBeInTheDocument()
    expect(screen.getByText('Titulares')).toBeInTheDocument()
    expect(screen.getByText('Suplentes')).toBeInTheDocument()

    // Comprobar contadores 3/3
    expect(screen.getAllByText('3/3')).toHaveLength(2)

    // Comprobar jugadores renderizados
    expect(screen.getByText('Jugador 1')).toBeInTheDocument()
    expect(screen.getByText('Jugador 6')).toBeInTheDocument()
  })

  it('Debe habilitar el botón de confirmación cuando la seleccion es 3 y 3', () => {
    render(<ChangeLineupModal {...defaultProps} />)

    const confirmBtn = screen.getByRole('button', { name: /confirmar alineación/i })
    expect(confirmBtn).toBeEnabled()
  })

  it('Debe deshabilitar el botón y mostrar alerta visual al romper la proporción de 3 titulares y 3 suplentes', async () => {
    const user = userEvent.setup()
    render(<ChangeLineupModal {...defaultProps} />)

    // Mover un titular a suplentes (quedan 2 titulares y 4 suplentes)
    const moveBtn = screen.getByRole('button', { name: /mover jugador 1 a suplentes/i })
    await user.click(moveBtn)

    // Contadores actualizados
    expect(screen.getByText('2/3')).toBeInTheDocument()
    expect(screen.getByText('4/3')).toBeInTheDocument()

    // El botón debe estar deshabilitado
    const confirmBtn = screen.getByRole('button', { name: /confirmar alineación/i })
    expect(confirmBtn).toBeDisabled()

    // Mensaje de advertencia visible
    expect(
      screen.getByText(/debes seleccionar exactamente 3 titulares y 3 suplentes/i)
    ).toBeInTheDocument()
  })

  it('Debe volver a habilitar el botón cuando el usuario reestablece el balance 3 y 3', async () => {
    const user = userEvent.setup()
    render(<ChangeLineupModal {...defaultProps} />)

    // 1. Desbalancear: mover titular a suplente
    const moveToSubBtn = screen.getByRole('button', { name: /mover jugador 1 a suplentes/i })
    await user.click(moveToSubBtn)

    const confirmBtn = screen.getByRole('button', { name: /confirmar alineación/i })
    expect(confirmBtn).toBeDisabled()

    // 2. Balancear: mover un suplente a titular
    const moveToStarterBtn = screen.getByRole('button', { name: /mover jugador 4 a titulares/i })
    await user.click(moveToStarterBtn)

    // 3. Vuelve a estar habilitado
    expect(confirmBtn).toBeEnabled()
  })

  it('Debe enviar el payload con el formato esperado a la API y llamar a onSuccess', async () => {
    const user = userEvent.setup()
    leaguesApi.update_league_lineup.mockResolvedValueOnce({ status: 'ok' })

    render(<ChangeLineupModal {...defaultProps} />)

    // Mover Jugador 1 a suplentes y Jugador 4 a titulares (intercambio)
    await user.click(screen.getByRole('button', { name: /mover jugador 1 a suplentes/i }))
    await user.click(screen.getByRole('button', { name: /mover jugador 4 a titulares/i }))

    const confirmBtn = screen.getByRole('button', { name: /confirmar alineación/i })
    await user.click(confirmBtn)

    // Verificar llamada al endpoint con los arrays formateados
    expect(leaguesApi.update_league_lineup).toHaveBeenCalledWith('league-123', {
      starters: ['p2', 'p3', 'p4'],
      substitutes: ['p5', 'p6', 'p1'],
    })

    // Verificar notificación de éxito y cierre del modal
    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalledWith(
        'Alineación actualizada. Se implementará a partir de tu siguiente partido'
      )
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1)
    })
  })

  it('Debe renderizar el mensaje de error del servidor si la petición falla y no cerrar el modal', async () => {
    const user = userEvent.setup()
    const errorMessage = 'No posees un club activo en esta liga'
    leaguesApi.update_league_lineup.mockRejectedValueOnce(new Error(errorMessage))

    render(<ChangeLineupModal {...defaultProps} />)

    const confirmBtn = screen.getByRole('button', { name: /confirmar alineación/i })
    await user.click(confirmBtn)

    expect(await screen.findByRole('alert')).toHaveTextContent(errorMessage)
    expect(defaultProps.onClose).not.toHaveBeenCalled()
  })
})