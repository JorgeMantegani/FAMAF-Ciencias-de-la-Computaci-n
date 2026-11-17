import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Home from '../src/pages/Home';
import ActiveRoomsModal from '../src/components/ActiveRoomsModal';
import * as authSession from '../src/auth/session';
import * as apiClient from '../src/api/client';

// Mock del cliente API
vi.mock('../src/api/client', () => ({
  get_current_user: vi.fn(),
  logout: vi.fn(),
}));

// Mock de react-router-dom para capturar navegaciones
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock nativo de WebSocket
class MockWebSocket {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.readyState = 1; // OPEN
    MockWebSocket.instances.push(this);
  }
  send = vi.fn();
  close = vi.fn(() => {
    if (this.onclose) this.onclose({ code: 1000 });
  });

  triggerMessage(data) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }
  triggerError() {
    if (this.onerror) this.onerror(new Event('error'));
  }
}

global.WebSocket = MockWebSocket;

describe('Ticket: Ver y Reingresar a Salas Activas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.instances = [];
    
    // CORRECCIÓN CLAVE: proveer un objeto de sesión completo que cumpla con read_session()
    vi.spyOn(authSession, 'read_session').mockReturnValue({
      access_token: 'fake-jwt-token-123',
      refresh_token: 'fake-refresh-token-456',
      club_id: 'club-uuid-abc',
      expires_at: Date.now() / 1000 + 3600,
    });

    // Mockear la respuesta exitosa del usuario actual
    apiClient.get_current_user.mockResolvedValue({ club_id: 'club-uuid-abc' });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // --- Pruebas de integración en Home.jsx ---
  describe('Integración con Home.jsx', () => {
    it('debe renderizar la tarjeta de Club y su botón VER SALAS ACTIVAS', async () => {
      render(
        <MemoryRouter>
          <Home />
        </MemoryRouter>
      );

      // Esperar a que el botón de salas activas aparezca en la tarjeta de Club
      const btnSalas = await screen.findByRole('button', { name: /VER SALAS ACTIVAS/i });
      expect(btnSalas).toBeInTheDocument();
      expect(screen.getByText('Club')).toBeInTheDocument();
    });

    it('debe abrir el modal ActiveRoomsModal al presionar VER SALAS ACTIVAS', async () => {
      render(
        <MemoryRouter>
          <Home />
        </MemoryRouter>
      );

      const btnSalas = await screen.findByRole('button', { name: /VER SALAS ACTIVAS/i });
      fireEvent.click(btnSalas);

      // Verificar que el modal se abrió mostrando su encabezado
      expect(screen.getByRole('heading', { name: /Salas Activas/i })).toBeInTheDocument();
    });
  });

  // --- Pruebas unitarias / funcionales de ActiveRoomsModal.jsx ---
  describe('Componente ActiveRoomsModal', () => {
    it('debe enviar el token de autenticación en la conexión WebSocket', () => {
      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      expect(MockWebSocket.instances.length).toBe(1);
      const wsInstance = MockWebSocket.instances[0];
      expect(wsInstance.url).toContain('/ws/rooms/active?token=fake-jwt-token-123');
    });

    it('debe mostrar mensaje de error si no hay sesión o token activo', () => {
      vi.spyOn(authSession, 'read_session').mockReturnValue(null);

      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      expect(screen.getByText('No hay sesión activa.')).toBeInTheDocument();
    });

    it('debe mostrar mensaje cuando no hay salas activas disponibles', async () => {
      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      const wsInstance = MockWebSocket.instances[0];
      wsInstance.triggerMessage([]);

      await waitFor(() => {
        expect(screen.getByText('No hay salas activas en este momento.')).toBeInTheDocument();
      });
    });

    it('debe listar correctamente salas de tipo Amistoso y Liga con su nombre y estado', async () => {
      const mockRooms = [
        { id: 'room-1', code: 'FRND99', type: 'friendly', status: 'waiting_guest' },
        { id: 'room-2', code: 'LEAG10', type: 'public', status: 'waiting_guest', name: 'Copa de Campeones' }
      ];

      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      const wsInstance = MockWebSocket.instances[0];
      wsInstance.triggerMessage(mockRooms);

      await waitFor(() => {
        expect(screen.getByText('Amistoso (FRND99)')).toBeInTheDocument();
        expect(screen.getByText('Copa de Campeones')).toBeInTheDocument();
      });

      expect(screen.getByText('Amistoso')).toBeInTheDocument();
      expect(screen.getByText('Liga')).toBeInTheDocument();
    });

    it('debe redirigir al lobby de amistosos al presionar Reingresar en un amistoso', async () => {
      const mockRooms = [
        { id: 'room-friendly-1', code: 'CODE123', type: 'friendly', status: 'waiting_guest' }
      ];

      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      const wsInstance = MockWebSocket.instances[0];
      wsInstance.triggerMessage(mockRooms);

      const reingresarBtn = await screen.findByRole('button', { name: /Reingresar/i });
      fireEvent.click(reingresarBtn);

      expect(mockNavigate).toHaveBeenCalledWith('/friendly/join', {
        state: { room_id: 'room-friendly-1', code: 'CODE123' }
      });
    });

    it('debe redirigir al lobby de espera de liga al presionar Reingresar en una liga', async () => {
      const mockRooms = [
        { id: 'league-uuid-456', code: 'LIGA99', type: 'public', status: 'waiting_guest', name: 'Superliga' }
      ];

      render(
        <MemoryRouter>
          <ActiveRoomsModal open={true} onClose={() => {}} />
        </MemoryRouter>
      );

      const wsInstance = MockWebSocket.instances[0];
      wsInstance.triggerMessage(mockRooms);

      const reingresarBtn = await screen.findByRole('button', { name: /Reingresar/i });
      fireEvent.click(reingresarBtn);

      expect(mockNavigate).toHaveBeenCalledWith('/league/league-uuid-456/waiting');
    });
  });
});