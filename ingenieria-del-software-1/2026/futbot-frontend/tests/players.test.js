import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createPlayer } from '../src/api/players.js';
import { save_session, clear_session } from '../src/auth/session.js';

// Mock de fetch para simular las respuestas de la API
describe('createPlayer', () => {
  beforeEach(() => {
    clear_session();
    vi.restoreAllMocks();
    vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    clear_session();
    vi.restoreAllMocks();
  });

  // Test para verificar que se realiza un POST a /api/players con el token y el payload correcto
  it('Debe realizar un POST a /api/players con el token y el payload correcto', async () => {
    save_session({
      access_token: 'token-de-prueba',
      refresh_token: 'refresh-de-prueba',
      club_id: 'club-123',
      expires_at: Math.floor(Date.now() / 1000) + 3600,
    });

    const mock_response = {
      id: 'player-123',
      name: 'Messi',
      power: 60,
      agility: 60,
      control: 60,
      speed: 60,
      strength: 60,
    };

    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(mock_response), {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    const result = await createPlayer({
      name: ' Messi ',
      power: '60',
      agility: '60',
      control: '60',
      speed: '60',
      strength: '60',
    });

    expect(fetch).toHaveBeenCalledTimes(1);

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe('http://localhost:8000/api/players');
    expect(options.method).toBe('POST');

    expect(options.headers.get('Authorization')).toBe(
      'Bearer token-de-prueba',
    );

    expect(options.headers.get('Content-Type')).toBe(
      'application/json',
    );

    expect(JSON.parse(options.body)).toEqual({
      name: 'Messi',
      power: 60,
      agility: 60,
      control: 60,
      speed: 60,
      strength: 60,
    });

    expect(result).toEqual(mock_response);
  });

  it('Debe rechazar la creación si no existe una sesión', async () => {
    await expect(
      createPlayer({
        name: 'Messi',
        power: '60',
        agility: '60',
        control: '60',
        speed: '60',
        strength: '60',
      }),
    ).rejects.toThrow(
      'Tu sesión venció. Iniciá sesión de nuevo.',
    );

    expect(fetch).not.toHaveBeenCalled();
  });
});
