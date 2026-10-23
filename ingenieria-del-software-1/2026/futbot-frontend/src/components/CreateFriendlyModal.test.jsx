import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CreateFriendlyModal from './CreateFriendlyModal'
import * as friendlyApi from '../api/friendly'

// Mock de las funciones de la API
vi.mock('../api/friendly', () => ({
  createFriendlyRoom: vi.fn(),
  getMyPlayers: vi.fn(),
  getMyBehaviors: vi.fn(),
}))

const mockPlayers = [
  { id: '1', name: 'Jugador 1' },
  { id: '2', name: 'Jugador 2' },
  { id: '3', name: 'Jugador 3' },
  { id: '4', name: 'Jugador 4' },
  { id: '5', name: 'Jugador 5' },
  { id: '6', name: 'Jugador 6' },
]

const mockBehaviors = [
  { id: '10', name: 'Estrategia 1', is_preprogrammed: true },
  { id: '20', name: 'Estrategia 2', is_preprogrammed: false },
]

describe('CreateFriendlyModal Component', () => {
  const handleClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    friendlyApi.getMyPlayers.mockResolvedValue(mockPlayers)
    friendlyApi.getMyBehaviors.mockResolvedValue(mockBehaviors)
  })

  it('no renderiza nada cuando isOpen es false', () => {
    const { container } = render(
      <CreateFriendlyModal isOpen={false} onClose={handleClose} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('carga y muestra los datos iniciales cuando se abre el modal', async () => {
    render(<CreateFriendlyModal isOpen={true} onClose={handleClose} />)

    expect(screen.getByText('Crear Partido Amistoso')).toBeInTheDocument()

    // Verificamos que se llamaron los servicios de la API
    await waitFor(() => {
      expect(friendlyApi.getMyPlayers).toHaveBeenCalledTimes(1)
      expect(friendlyApi.getMyBehaviors).toHaveBeenCalledTimes(1)
    })

    // Verificamos que los selectores de jugadores y estrategias estén cargados
    const playerOptions = await screen.findAllByRole('option', { name: /Jugador 1/i })
    expect(playerOptions.length).toBeGreaterThan(0)
  })

  it('muestra un mensaje de error si falla la carga inicial de jugadores o estrategias', async () => {
    friendlyApi.getMyPlayers.mockRejectedValueOnce(new Error('Network Error'))

    render(<CreateFriendlyModal isOpen={true} onClose={handleClose} />)

    await waitFor(() => {
      expect(
        screen.getByText('Error al cargar la pantalla de jugadores y estrategias.')
      ).toBeInTheDocument()
    })
  })

  it('deshabilita el botón de confirmación si la alineación está incompleta', async () => {
    render(<CreateFriendlyModal isOpen={true} onClose={handleClose} />)

    await waitFor(() => {
      expect(friendlyApi.getMyPlayers).toHaveBeenCalled()
    })

    const confirmBtn = screen.getByRole('button', { name: /Confirmar y Crear Sala/i })
    expect(confirmBtn).toBeDisabled()
  })

  it('permite completar el equipo, habilitar el botón y crear la sala exitosamente', async () => {
    const mockCreatedRoom = {
      room_code: 'ROOM123',
      room_id: 'abc-456-id',
    }
    friendlyApi.createFriendlyRoom.mockResolvedValueOnce(mockCreatedRoom)

    const user = userEvent.setup()
    render(<CreateFriendlyModal isOpen={true} onClose={handleClose} />)

    // Esperar a que se carguen los selectores
    await waitFor(() => expect(friendlyApi.getMyPlayers).toHaveBeenCalled())

    // Obtener todos los selectores del formulario (6 de jugador + 6 de estrategia = 12 selectores)
    const selects = screen.getAllByRole('combobox')
    expect(selects.length).toBe(12)

    // Seleccionar 6 jugadores distintos y 6 estrategias
    // Los pares (0, 1), (2, 3), (4, 5) corresponden a los 3 titulares
    // Los pares (6, 7), (8, 9), (10, 11) corresponden a los 3 suplentes
    for (let i = 0; i < 6; i++) {
      const playerSelect = selects[i * 2]
      const behaviorSelect = selects[i * 2 + 1]

      await user.selectOptions(playerSelect, mockPlayers[i].id)
      await user.selectOptions(behaviorSelect, mockBehaviors[0].id)
    }

    const confirmBtn = screen.getByRole('button', { name: /Confirmar y Crear Sala/i })
    expect(confirmBtn).not.toBeDisabled()

    // Enviar el formulario
    await user.click(confirmBtn)

    // Verificar que se haya llamado a createFriendlyRoom con la carga útil formateada
    await waitFor(() => {
      expect(friendlyApi.createFriendlyRoom).toHaveBeenCalledWith({
        starters: [
          { player_id: '1', behavior_id: '10' },
          { player_id: '2', behavior_id: '10' },
          { player_id: '3', behavior_id: '10' },
        ],
        substitutes: [
          { player_id: '4', behavior_id: '10' },
          { player_id: '5', behavior_id: '10' },
          { player_id: '6', behavior_id: '10' },
        ],
      })
    })

    // Verificar la pantalla de éxito
    expect(await screen.findByText('¡Amistoso Creado Exitosamente!')).toBeInTheDocument()
    expect(screen.getByText('ROOM123')).toBeInTheDocument()
    expect(screen.getByText('ID: abc-456-id')).toBeInTheDocument()
  })

  it('muestra un mensaje de error si falla la creación de la sala', async () => {
    friendlyApi.createFriendlyRoom.mockRejectedValueOnce({
      detail: 'No hay cupo disponible',
    })

    const user = userEvent.setup()
    render(<CreateFriendlyModal isOpen={true} onClose={handleClose} />)

    await waitFor(() => expect(friendlyApi.getMyPlayers).toHaveBeenCalled())

    const selects = screen.getAllByRole('combobox')
    for (let i = 0; i < 6; i++) {
      await user.selectOptions(selects[i * 2], mockPlayers[i].id)
      await user.selectOptions(selects[i * 2 + 1], mockBehaviors[0].id)
    }

    const confirmBtn = screen.getByRole('button', { name: /Confirmar y Crear Sala/i })
    await user.click(confirmBtn)

    // Esperar mensaje de error
    await waitFor(() => {
      expect(screen.getByText('No hay cupo disponible')).toBeInTheDocument()
    })
  })

  it('llama a la función onClose al hacer clic en el botón de cancelar o en el fondo', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <CreateFriendlyModal isOpen={true} onClose={handleClose} />
    )

    const cancelBtn = screen.getByRole('button', { name: /Cancelar/i })
    await user.click(cancelBtn)

    expect(handleClose).toHaveBeenCalledTimes(1)

    // Clic en el overlay del modal
    const overlay = container.querySelector('.modal-overlay')
    await user.click(overlay)

    expect(handleClose).toHaveBeenCalledTimes(2)
  })
})