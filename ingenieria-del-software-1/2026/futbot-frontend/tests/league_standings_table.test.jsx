import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import LeagueStandingsTable from '../src/components/LeagueStandingsTable';
import { getLeagueStandings } from '../src/api/leagues';

vi.mock('../src/api/leagues', () => ({
  getLeagueStandings: vi.fn(),
}));

describe('LeagueStandingsTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza los puntos devueltos por el backend para una victoria por penales', async () => {
    getLeagueStandings.mockResolvedValue([
      {
        club_id: 'club-winner',
        club_name: 'Club ganador',
        matches_played: 1,
        matches_won: 1,
        matches_drawn: 0,
        matches_lost: 0,
        goals_for: 2,
        goals_against: 2,
        goal_difference: 0,
        points: 2,
      },
      {
        club_id: 'club-loser',
        club_name: 'Club perdedor',
        matches_played: 1,
        matches_won: 0,
        matches_drawn: 0,
        matches_lost: 1,
        goals_for: 2,
        goals_against: 2,
        goal_difference: 0,
        points: 0,
      },
    ]);

    render(<LeagueStandingsTable leagueId="league-1" />);

    const table = await screen.findByRole('table');
    const winner = within(table).getByRole('row', { name: /club ganador/i });
    const loser = within(table).getByRole('row', { name: /club perdedor/i });

    expect(within(winner).getAllByRole('cell').at(-1).textContent).toBe('2');
    expect(within(loser).getAllByRole('cell').at(-1).textContent).toBe('0');
    expect(getLeagueStandings).toHaveBeenCalledWith(
      'league-1',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });
});
