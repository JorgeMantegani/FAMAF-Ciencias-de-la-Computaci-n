import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { use_league_waiting_socket } from '../src/hooks/use_league_waiting_socket';

// Mock global de WebSocket
class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = WebSocket.OPEN;
    MockWebSocket.instances.push(this);
  }
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = WebSocket.CLOSED;
  });
}

MockWebSocket.instances = [];
MockWebSocket.OPEN = 1;
MockWebSocket.CLOSED = 3;

describe('use_league_waiting_socket Hook', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    MockWebSocket.instances = [];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('debe conectarse al WebSocket y recibir información inicial de la sala (room_info)', () => {
    const { result } = renderHook(() => use_league_waiting_socket('league-123', 'club-456'));

    expect(MockWebSocket.instances.length).toBe(1);
    expect(MockWebSocket.instances[0].url).toContain('/ws/league/league-123/waiting?club_id=club-456');

    // Simular la llegada de un mensaje del servidor
    act(() => {
      const wsInstance = MockWebSocket.instances[0];
      wsInstance.onmessage({
        data: JSON.stringify({
          type: 'room_info',
          league_id: 'league-123',
          league_name: 'Liga de Prueba',
          creator_club_id: 'club-456',
          current_participants: 1,
          min_clubs: 3,
          max_clubs: 5,
          inscribed_clubs: ['club-456']
        })
      });
    });

    expect(result.current.room_info).not.toBeNull();
    expect(result.current.room_info.league_name).toBe('Liga de Prueba');
    expect(result.current.room_info.current_participants).toBe(1);
  });

  it('debe permitir enviar acciones al servidor a través del socket', () => {
    const { result } = renderHook(() => use_league_waiting_socket('league-123', 'club-456'));

    act(() => {
      result.current.send_action('start_league');
    });

    const wsInstance = MockWebSocket.instances[0];
    expect(wsInstance.send).toHaveBeenCalledWith(JSON.stringify({ action: 'start_league' }));
  });
});