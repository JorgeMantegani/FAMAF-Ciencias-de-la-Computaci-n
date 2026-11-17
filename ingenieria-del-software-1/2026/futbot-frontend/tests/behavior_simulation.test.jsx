import { render, screen, act, renderHook, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import SquadSelector from '../src/components/SquadSelector'
import MiniPitchViewer from '../src/components/mini_pitch_viewer.jsx'
import CreateLeagueForm from '../src/components/create_league_form'
import { useBehaviorSimulation } from '../src/hooks/use_behavior_simulation'
import * as behaviorsApi from '../src/api/behaviors.js'

// Mock de la API de behaviors
vi.mock('../src/api/behaviors.js', () => ({
  connect_to_simulation_ticket: vi.fn(),
  create_simulation_ticket: vi.fn(),
}))

// Mock de la API de friendly para obtener jugadores y comportamientos
vi.mock('../src/api/friendly', () => ({
  getMyPlayers: vi.fn().mockResolvedValue([{ id: 'player-1', name: 'Jugador 1' }]),
  getMyBehaviors: vi.fn().mockResolvedValue([{ id: 'behavior-1', name: 'Estrategia 1' }]),
}))

describe('Simulación de Comportamientos', () => {
  let mockSocket

  beforeEach(() => {
    vi.clearAllMocks()

    mockSocket = {
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      close: vi.fn(),
      readyState: 1, // OPEN
    }

    behaviorsApi.create_simulation_ticket.mockResolvedValue({ ticket: 'ticket-123' })
    behaviorsApi.connect_to_simulation_ticket.mockReturnValue(mockSocket)
  })

  describe('SquadSelector UI', () => {
    const mockPlayers = [{ id: 'player-1', name: 'Jugador 1' }]
    const mockBehaviors = [{ id: 'behavior-1', name: 'Estrategia 1' }]
    const squadVacio = {
      starters: [
        { playerId: '', behaviorId: '' },
        { playerId: '', behaviorId: '' },
        { playerId: '', behaviorId: '' },
      ],
      substitutes: [
        { playerId: '', behaviorId: '' },
        { playerId: '', behaviorId: '' },
        { playerId: '', behaviorId: '' },
      ],
    }

    it('Debe deshabilitar el botón sin selección y habilitarlo al elegir escuadra', async () => {
      const user = userEvent.setup()
      const onPreviewMock = vi.fn()

      const { rerender } = render(
        <SquadSelector
          players={mockPlayers}
          behaviors={mockBehaviors}
          squad={squadVacio}
          setSquad={vi.fn()}
          onPreview={onPreviewMock}
        />
      )

      const buttons = screen.getAllByRole('button', { name: /probar comportamiento/i })
      expect(buttons[0]).toBeDisabled()

      const squadLleno = {
        ...squadVacio,
        starters: [
          { playerId: 'player-1', behaviorId: 'behavior-1' },
          { playerId: '', behaviorId: '' },
          { playerId: '', behaviorId: '' },
        ],
      }

      rerender(
        <SquadSelector
          players={mockPlayers}
          behaviors={mockBehaviors}
          squad={squadLleno}
          setSquad={vi.fn()}
          onPreview={onPreviewMock}
        />
      )

      const enabledButtons = screen.getAllByRole('button', { name: /probar comportamiento/i })
      expect(enabledButtons[0]).toBeEnabled()

      await user.click(enabledButtons[0])
      expect(onPreviewMock).toHaveBeenCalledWith({
        playerId: 'player-1',
        behaviorId: 'behavior-1',
      })
    })
  })

  describe('Hook useBehaviorSimulation', () => {
    it('Debe tener estado connecting al iniciar, pasar a online al conectar y capturar ticks', async () => {
      const { result } = renderHook(() => useBehaviorSimulation('player-1', 'behavior-1'))

      await waitFor(() => {
        expect(behaviorsApi.create_simulation_ticket).toHaveBeenCalledWith('player-1', 'behavior-1')
        expect(behaviorsApi.connect_to_simulation_ticket).toHaveBeenCalledWith('ticket-123')
      })

      expect(result.current.connectionStatus).toBe('connecting')

      act(() => {
        if (mockSocket.onopen) mockSocket.onopen()
      })
      expect(result.current.connectionStatus).toBe('online')

      const mockTick = {
        type: 'tick',
        players: [{ id: 'player-1', team: 'HOME', position: { x: 10, y: 10 } }],
        ball: { position: { x: 12, y: 10 }, owner_id: 'player-1' },
      }

      act(() => {
        if (mockSocket.onmessage) {
          mockSocket.onmessage({ data: JSON.stringify(mockTick) })
        }
      })
      expect(result.current.simulationData).toEqual(mockTick)
    })

    it('Debe cerrar el WebSocket adecuadamente al desmontar el hook', async () => {
      const { unmount } = renderHook(() => useBehaviorSimulation('player-1', 'behavior-1'))

      await waitFor(() => {
        expect(behaviorsApi.connect_to_simulation_ticket).toHaveBeenCalledWith('ticket-123')
      })

      unmount()
      expect(mockSocket.close).toHaveBeenCalled()
    })
  })

  describe('MiniPitchViewer y MatchPitch Render', () => {
    it('Debe mostrar la cancha y los jugadores tras recibir ticks y permitir cerrar el modal', async () => {
      const user = userEvent.setup()
      const onCloseMock = vi.fn()

      const mockTick = {
        type: 'tick',
        players: [
          { id: 'player-1', team: 'HOME', position: { x: 10, y: 10 } },
          { id: 'rival-1', team: 'AWAY', position: { x: 50, y: 50 } },
        ],
        ball: { position: { x: 12, y: 10 }, owner_id: 'player-1' },
      }

      const { container } = render(
        <MiniPitchViewer player_id="player-1" behavior_id="behavior-1" onClose={onCloseMock} />
      )

      // Se espera a que se resuelva la llamada a la API antes de simular el socket
      await waitFor(() => {
        expect(behaviorsApi.create_simulation_ticket).toHaveBeenCalledWith('player-1', 'behavior-1')
        expect(behaviorsApi.connect_to_simulation_ticket).toHaveBeenCalledWith('ticket-123')
      })

      // Emitir eventos del socket
      act(() => {
        if (mockSocket.onopen) mockSocket.onopen()
        if (mockSocket.onmessage) {
          mockSocket.onmessage({ data: JSON.stringify(mockTick) })
        }
      })

      // Verificar que el SVG de la cancha se renderizó
      expect(container.querySelector('svg')).toBeInTheDocument()

      // Probar el botón de cierre
      const closeBtn = screen.getByRole('button', { name: /cerrar prueba/i })
      await user.click(closeBtn)

      expect(onCloseMock).toHaveBeenCalledTimes(1)
    })
  })

  describe('Integración en Formulario de Registro de Liga', () => {
    it('Debe disparar POST para ticket y despliegar el visor al hacer click en probar', async () => {
      const user = userEvent.setup()

      behaviorsApi.create_simulation_ticket.mockResolvedValue({ ticket: 'ticket-simulacion-999' })

      render(
        <MemoryRouter>
          <CreateLeagueForm onCancel={vi.fn()} />
        </MemoryRouter>
      )

      const selects = await screen.findAllByRole('combobox')

      await user.selectOptions(selects[0], 'player-1')
      await user.selectOptions(selects[1], 'behavior-1')

      const previewButton = screen.getAllByRole('button', { name: /probar comportamiento/i })[0]
      await user.click(previewButton)

      expect(behaviorsApi.create_simulation_ticket).toHaveBeenCalledWith('player-1', 'behavior-1')

      await waitFor(() => {
        expect(behaviorsApi.connect_to_simulation_ticket).toHaveBeenCalledWith('ticket-simulacion-999')
      })

      expect(await screen.findByText(/prueba de comportamiento/i)).toBeInTheDocument()
    })
  })
})