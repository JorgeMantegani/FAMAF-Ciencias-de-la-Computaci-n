import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LeagueWaitingRoom from '../src/pages/league_waiting_room';
import * as sessionModule from '../src/auth/session';
import * as socketModule from '../src/hooks/use_league_waiting_socket';

vi.mock('../src/auth/session');
vi.mock('../src/hooks/use_league_waiting_socket');

describe('LeagueWaitingRoom Component', () => {
  const mockSendAction = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(sessionModule, 'read_session').mockReturnValue({ club_id: 'creator-club' });
  });

  it('muestra el mensaje de carga inicial cuando no hay room_info', () => {
    socketModule.use_league_waiting_socket.mockReturnValue({
      room_info: null,
      error: null,
      redirect_url: null,
      send_action: mockSendAction
    });

    render(
      <MemoryRouter>
        <LeagueWaitingRoom />
      </MemoryRouter>
    );

    expect(screen.getByText('Conectando al lobby de la liga...')).not.toBeNull();
  });

  it('renderiza como creador con el botón Iniciar deshabilitado si no se alcanza el mínimo', () => {
    socketModule.use_league_waiting_socket.mockReturnValue({
      room_info: {
        league_name: 'Liga Test',
        creator_club_id: 'creator-club',
        creator_club_name: 'Mi Club',
        current_participants: 1,
        min_clubs: 3,
        max_clubs: 5,
        inscribed_clubs: ['creator-club']
      },
      error: null,
      redirect_url: null,
      send_action: mockSendAction
    });

    render(
      <MemoryRouter>
        <LeagueWaitingRoom />
      </MemoryRouter>
    );

    expect(screen.getByText('Lobby de Espera: Liga Test')).not.toBeNull();
    const startButton = screen.getByRole('button', { name: 'Iniciar Liga' });
    expect(startButton.disabled).toBe(true);
  });
});