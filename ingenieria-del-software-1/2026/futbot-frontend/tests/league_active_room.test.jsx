import { render, screen, act, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import OngoingLeagueLobbyView from '../src/pages/league_active_room';
import * as sessionModule from '../src/auth/session';

vi.mock('../src/auth/session', () => ({
    read_session: vi.fn()
}));

globalThis.fetch = vi.fn();

// Mock global de WebSocket para simular tiempo real
class MockWebSocket {
    constructor(url) {
        MockWebSocket.instances.push(this);
        this.url = url;
    }
    send = vi.fn();
    close = vi.fn();
}
MockWebSocket.instances = [];
globalThis.WebSocket = MockWebSocket;

describe('OngoingLeagueLobbyView - Suite Exhaustiva', () => {
    const mock_session = {
        token: 'fake-jwt-token',
        club_id: 'club-1'
    };

    const mock_lobby_payload = {
        league_id: 'league-123',
        league_name: 'Liga Estelar',
        status: 'in_progress',
        currentMatch: {
            id: 'm-1',
            round: 1,
            home_club_id: 'club-1',
            away_club_id: 'club-2',
            home_club_name: 'Club Alfa',
            away_club_name: 'Club Beta',
            home_score: 1,
            away_score: 0,
            status: 'in_progress'
        },
        nextMatch: {
            id: 'm-2',
            round: 2,
            home_club_name: 'Club Beta',
            away_club_name: 'Club Gamma'
        },
        standings: [
            { club_id: 'club-1', club_name: 'Club Alfa', points: 3, matches_played: 1, matches_won: 1, matches_drawn: 0, matches_lost: 0, goals_for: 1, goals_against: 0, goal_difference: 1 },
            { club_id: 'club-2', club_name: 'Club Beta', points: 0, matches_played: 1, matches_won: 0, matches_drawn: 0, matches_lost: 1, goals_for: 0, goals_against: 1, goal_difference: -1 }
        ],
        calendar: [
            { id: 'm-1', round: 1, home_club_name: 'Club Alfa', away_club_name: 'Club Beta', home_score: 1, away_score: 0, status: 'finished' }
        ]
    };

    beforeEach(() => {
        MockWebSocket.instances = [];
        vi.spyOn(sessionModule, 'read_session').mockReturnValue(mock_session);
        globalThis.fetch.mockReset().mockResolvedValue({
            ok: true,
            json: async () => mock_lobby_payload
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it('1. Renderiza correctamente el lobby con el fetch inicial y destaca al club del usuario', async () => {
        render(
            <MemoryRouter initialEntries={['/league/league-123/active']}>
                <Routes>
                    <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
                </Routes>
            </MemoryRouter>
        );

        expect(await screen.findByText('Liga Estelar')).toBeInTheDocument();
        expect(screen.getAllByText('Club Alfa').length).toBeGreaterThan(0);
        expect(screen.getAllByText('1 - 0').length).toBeGreaterThan(0);

        const my_club_row = screen.getByText('Club Alfa (Tú)').closest('tr');
        expect(my_club_row).toHaveClass('my-club-row');
    });

    it('2. Muestra la información del próximo encuentro y el calendario correctamente', async () => {
        render(
            <MemoryRouter initialEntries={['/league/league-123/active']}>
                <Routes>
                    <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
                </Routes>
            </MemoryRouter>
        );

        expect(await screen.findByText('Próximo Encuentro (Next Match)')).toBeInTheDocument();
        expect(screen.getByText('Club Gamma')).toBeInTheDocument();
        expect(screen.getByText('Calendario del Torneo')).toBeInTheDocument();
    });

    it('3. Reacciona a los mensajes del WebSocket actualizando la UI y mostrando el Toast', async () => {
        render(
            <MemoryRouter initialEntries={['/league/league-123/active']}>
                <Routes>
                    <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
                </Routes>
            </MemoryRouter>
        );

        await screen.findByText('Liga Estelar');

        // Obtener la instancia del WebSocket creada por el hook
        const ws_instance = MockWebSocket.instances[0];
        expect(ws_instance).toBeDefined();

        // Simular la llegada de un mensaje en tiempo real por el WS
        const ws_message = {
            type: 'match_update',
            payload: {
                currentMatch: {
                    id: 'm-2',
                    round: 2,
                    home_club_id: 'club-2',
                    away_club_id: 'club-3',
                    home_club_name: 'Club Beta',
                    away_club_name: 'Club Gamma',
                    home_score: 2,
                    away_score: 2,
                    status: 'in_progress'
                }
            },
            toast: 'Partido finalizado: Club Alfa 1 - 0 Club Beta'
        };

        act(() => {
            ws_instance.onmessage({ data: JSON.stringify(ws_message) });
        });

        // Validar que el Toast sutil aparece en pantalla
        expect(await screen.findByText(/Partido finalizado: Club Alfa 1 - 0 Club Beta/i)).toBeInTheDocument();
        
        // Validar que el partido actual cambió en la vista en tiempo real
        expect(screen.getByText('2 - 2')).toBeInTheDocument();
    });

    it('4. Maneja adecuadamente el error de carga HTTP del lobby', async () => {
        globalThis.fetch.mockResolvedValueOnce({
            ok: false
        });

        render(
            <MemoryRouter initialEntries={['/league/league-123/active']}>
                <Routes>
                    <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
                </Routes>
            </MemoryRouter>
        );

        expect(await screen.findByText(/Error al cargar la liga/i)).toBeInTheDocument();
    });

    it.each(['antes', 'después'])('muestra el partido por WebSocket %s del HTTP inicial', async (order) => {
        const user = userEvent.setup();
        const waiting = { ...mock_lobby_payload, currentMatch: null };
        let resolveFetch;
        globalThis.fetch.mockReturnValueOnce(new Promise((resolve) => { resolveFetch = resolve; }));
        render(
            <MemoryRouter initialEntries={['/league/league-123/active']}>
                <Routes>
                    <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
                    <Route path="/matches/m-1" element={<h1>Partido m-1</h1>} />
                </Routes>
            </MemoryRouter>
        );
        const respond = () => resolveFetch({ ok: true, json: async () => waiting });
        if (order === 'después') {
            await act(async () => respond());
            expect(screen.queryByRole('button', { name: /Ver Transmisión en Vivo/ })).not.toBeInTheDocument();
        }
        // Formato real de get_league_lobby_payload, sin contenedor "payload".
        act(() => MockWebSocket.instances[0].onmessage({
            data: JSON.stringify({ type: 'league_lobby_update', ...mock_lobby_payload }),
        }));
        expect(await screen.findByRole('button', { name: /Ver Transmisión en Vivo/ })).toBeInTheDocument();
        if (order === 'antes') await act(async () => respond());
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        await user.click(screen.getByRole('button', { name: /Ver Transmisión en Vivo/ }));
        expect(screen.getByRole('heading', { name: 'Partido m-1' })).toBeInTheDocument();
    });

    it('actualiza el cierre de la liga con el mensaje real del servidor', async () => {
        render(<MemoryRouter initialEntries={['/league/league-123/active']}>
            <Routes>
                <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
            </Routes>
        </MemoryRouter>);
        await screen.findByText('Liga Estelar');
        act(() => MockWebSocket.instances[0].onmessage({ data: JSON.stringify({
            type: 'league_lobby_update', ...mock_lobby_payload,
            status: 'finished', currentMatch: null, nextMatch: null,
        }) }));
        expect(await screen.findByText(/El torneo ha finalizado/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Ver Transmisión en Vivo/ })).not.toBeInTheDocument();
    });

    it.each([
        ['antes', false], ['antes', true], ['después', false], ['después', true],
    ])('conserva la plantilla HTTP con WS %s (envuelto: %s)', async (order, wrapped) => {
        const user = userEvent.setup();
        const squad = Array.from({ length: 6 }, (_, index) => ({
            player_id: `player-${index}`, name: `Jugador ${index + 1}`,
            role: index < 3 ? 'starter' : 'substitute',
        }));
        let resolveFetch;
        globalThis.fetch.mockReturnValueOnce(new Promise((resolve) => { resolveFetch = resolve; }));
        render(<MemoryRouter initialEntries={['/league/league-123/active']}>
            <Routes>
                <Route path="/league/:league_id/active" element={<OngoingLeagueLobbyView />} />
            </Routes>
        </MemoryRouter>);
        const respond = () => resolveFetch({
            ok: true,
            json: async () => ({ ...mock_lobby_payload, currentMatch: null, my_squad: squad }),
        });
        if (order === 'después') await act(async () => respond());

        const snapshot = {
            ...mock_lobby_payload, my_squad: [],
            currentMatch: { ...mock_lobby_payload.currentMatch, home_score: 2, away_score: 2 },
        };
        const message = wrapped
            ? { type: 'league_lobby_update', payload: snapshot }
            : { type: 'league_lobby_update', ...snapshot };
        const push = () => MockWebSocket.instances[0].onmessage({ data: JSON.stringify(message) });
        act(push);
        if (order === 'antes') {
            expect(screen.queryByRole('button', { name: /Cambiar alineación/i })).not.toBeInTheDocument();
            await act(async () => respond());
        }
        // El HTTP tardío aporta la plantilla sin volver al estado anterior del partido.
        expect(screen.getByText('2 - 2')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Ver Transmisión en Vivo/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Cambiar alineación/i })).toBeInTheDocument();
        // Los siguientes snapshots tampoco deben borrar la plantilla del usuario.
        act(push);
        await user.click(screen.getByRole('button', { name: /Cambiar alineación/i }));
        const modal = screen.getByRole('dialog');
        for (const player of squad) expect(within(modal).getByText(player.name)).toBeInTheDocument();
        expect(within(modal).getAllByText('3/3')).toHaveLength(2);
    });
});
