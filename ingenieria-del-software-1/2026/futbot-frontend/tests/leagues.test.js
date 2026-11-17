import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  apply_league_list,
  createLeague,
  find_league_by_code,
  free_spots,
  get_league,
  getLeagueStandings,
  is_league_full,
  join_league,
  OPEN_LEAGUE_STATUSES,
} from "../src/api/leagues.js";
import { request } from "../src/api/client";
import { read_session } from "../src/auth/session";

vi.mock('../src/api/client', () => ({ request: vi.fn() }))
vi.mock('../src/auth/session', () => ({ read_session: vi.fn() }))

beforeEach(() => {
  vi.resetAllMocks()
})

describe('free_spots and is_league_full', () => {
  it('counts the free spots and never goes below zero', () => {
    expect(free_spots({ maxClubs: 8, enrolledClubs: 5 })).toBe(3)
    expect(free_spots({ maxClubs: 3, enrolledClubs: 4 })).toBe(0)
  })

  it('a league is full when every spot is taken', () => {
    expect(is_league_full({ maxClubs: 3, enrolledClubs: 2 })).toBe(false)
    expect(is_league_full({ maxClubs: 3, enrolledClubs: 3 })).toBe(true)
  })
})

describe('get_league', () => {
  it('requests the league with an encoded id and forwards the options', () => {
    const { signal } = new AbortController()

    get_league('liga/1', { signal })

    expect(request).toHaveBeenCalledWith('/api/leagues/liga%2F1', { signal })
  })
})

describe('find_league_by_code', () => {
  it('requests the league with an encoded code and forwards the options', () => {
    const { signal } = new AbortController()

    find_league_by_code('a b/c', { signal })

    expect(request).toHaveBeenCalledWith('/api/leagues/by-code/a%20b%2Fc', { signal })
  })
})

describe('apply_league_list', () => {
  const league = {
    leagueId: 'league-1',
    name: 'Liga del Barrio',
    status: 'waitingGuest',
    enrolledClubs: 2,
    maxClubs: 8,
  }
  const listed = (overrides = {}) => ({
    id: 'league-1',
    name: 'Liga del Barrio',
    participants_count: 3,
    started: false,
    ...overrides,
  })

  it('updates the enrolled clubs and keeps the rest of the detail', () => {
    expect(apply_league_list(league, [listed()])).toEqual({ ...league, enrolledClubs: 3 })
  })

  it('moves an open league to in progress when it started', () => {
    expect(apply_league_list(league, [listed({ started: true })]).status).toBe('inProgress')
  })

  it('does not turn a finished league back to in progress', () => {
    const finished = { ...league, status: 'finished' }

    expect(apply_league_list(finished, [listed({ started: true })]).status).toBe('finished')
  })

  it('keeps the league untouched when the list does not include it', () => {
    expect(apply_league_list(league, [listed({ id: 'other-league' })])).toBe(league)
  })

  it('ignores the list until the league has loaded', () => {
    expect(apply_league_list(null, [listed()])).toBeNull()
  })
})

describe('join_league', () => {
  it('posts titulares and suplentes with string ids and no password', () => {
    join_league('league-1', {
      starters: [
        { playerId: 1, behaviorId: 10 },
        { playerId: 2, behaviorId: 10 },
        { playerId: 3, behaviorId: 20 },
      ],
      substitutes: [
        { playerId: 4, behaviorId: 10 },
        { playerId: 5, behaviorId: 20 },
        { playerId: 6, behaviorId: 20 },
      ],
    })

    const [path, options] = request.mock.calls[0]

    expect(path).toBe('/api/leagues/league-1/join')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({
      titulares: [
        { playerId: '1', behaviorId: '10' },
        { playerId: '2', behaviorId: '10' },
        { playerId: '3', behaviorId: '20' },
      ],
      suplentes: [
        { playerId: '4', behaviorId: '10' },
        { playerId: '5', behaviorId: '20' },
        { playerId: '6', behaviorId: '20' },
      ],
    })
    expect(JSON.parse(options.body)).not.toHaveProperty('password')
  })

  it('adds the password for a private league', () => {
    const slot = { playerId: 'p', behaviorId: 'b' }

    join_league('league-1', {
      starters: [slot, slot, slot],
      substitutes: [slot, slot, slot],
      password: 'secreta',
    })

    const [, options] = request.mock.calls[0]
    expect(JSON.parse(options.body).password).toBe('secreta')
  })
})

describe('OPEN_LEAGUE_STATUSES', () => {
  it('only accepts clubs while the league is waiting or ready to start', () => {
    expect(OPEN_LEAGUE_STATUSES).toEqual(['waitingGuest', 'readyToStart'])
  })
})

const players = (count, start) =>
  Array.from({ length: count }, (_, i) => ({
    playerId: start + i,
    behaviorId: start + i + 100,
  }));

const input = {
  name: "  Liga de prueba  ",
  is_private: false,
  min_clubs: "3",
  max_clubs: "30",
  match_duration: "90",
  starters: players(3, 1),
  substitutes: players(3, 4),
};

describe("createLeague", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    read_session.mockReturnValue({ access_token: "token-123" });
    request.mockResolvedValue({ code_to_join: "ABC123" });
  });

  it("hace POST a /api/leagues con el token", async () => {
    await createLeague(input);

    const [url, options] = request.mock.calls[0];
    expect(url).toBe("/api/leagues");
    expect(options.method).toBe("POST");
    expect(options.headers.Authorization).toBe("Bearer token-123");
  });

  it("envía el body en snake_case y con ids string", async () => {
    await createLeague(input);

    const body = JSON.parse(request.mock.calls[0][1].body);
    expect(body).toEqual({
      name: "Liga de prueba",
      is_private: false,
      has_penalty_shootout: false,
      min_clubs: 3,
      max_clubs: 30,
      match_duration: 90,
      starters: [
        { player_id: "1", behavior_id: "101" },
        { player_id: "2", behavior_id: "102" },
        { player_id: "3", behavior_id: "103" },
      ],
      substitutes: [
        { player_id: "4", behavior_id: "104" },
        { player_id: "5", behavior_id: "105" },
        { player_id: "6", behavior_id: "106" },
      ],
    });
  });

  it("devuelve la respuesta del backend", async () => {
    await expect(createLeague(input)).resolves.toEqual({
      code_to_join: "ABC123",
    });
  });

  it("lanza error si no hay sesión y no llama al backend", async () => {
    read_session.mockReturnValue(null);

    await expect(createLeague(input)).rejects.toThrow(
      "Tu sesión venció. Iniciá sesión de nuevo."
    );
    expect(request).not.toHaveBeenCalled();
  });

  it("envía una liga pública sin password en el body", async () => {
    await createLeague(input);

    const body = JSON.parse(request.mock.calls[0][1].body);

    expect(body.is_private).toBe(false);
    expect("password" in body).toBe(false);
    expect(body.has_penalty_shootout).toBe(false);
  });

  it("envía has_penalty_shootout como booleano", async () => {
    await createLeague({ ...input, has_penalty_shootout: true });

    const body = JSON.parse(request.mock.calls[0][1].body);

    expect(body.has_penalty_shootout).toBe(true);
    expect(typeof body.has_penalty_shootout).toBe("boolean");
  });

  it("envía is_private y password para una liga privada", async () => {
    const password = "abc123";

    await createLeague({
      ...input,
      is_private: true,
      password,
    });

    const body = JSON.parse(request.mock.calls[0][1].body);

    expect(body.is_private).toBe(true);
    expect(body.password).toBe(password);
  });
  it("consulta las posiciones de una liga por su endpoint", async () => {
    request.mockResolvedValue([]);

    await getLeagueStandings("league/1");

    expect(request).toHaveBeenCalledWith(
      "/api/leagues/league%2F1/standings",
      expect.objectContaining({ signal: undefined })
    );
  });
});
