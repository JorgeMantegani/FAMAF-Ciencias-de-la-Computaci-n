import { useEffect, useState } from 'react';
import { getLeagueStandings } from '../api/leagues';

export default function LeagueStandingsTable({ leagueId }) {
  const [result, setResult] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${leagueId}:${attempt}`;

  useEffect(() => {
    const controller = new AbortController();

    getLeagueStandings(leagueId, { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        const rows = Array.isArray(response) ? response : response?.standings;
        if (!Array.isArray(rows)) {
          throw new TypeError('La respuesta de posiciones no tiene un formato válido.');
        }
        setResult({ requestKey, status: 'ready', standings: rows });
      })
      .catch((cause) => {
        if (controller.signal.aborted || cause.name === 'AbortError') return;
        setResult({
          requestKey,
          status: 'error',
          error: cause.message || 'No se pudo cargar la tabla de posiciones.',
        });
      });

    return () => controller.abort();
  }, [leagueId, requestKey]);

  const currentResult = result?.requestKey === requestKey
    ? result
    : { status: 'loading', standings: [] };

  return (
    <section aria-labelledby="league-standings-title">
      <h3 id="league-standings-title" className="text-lg font-semibold text-white">
        Tabla de posiciones
      </h3>
      {currentResult.status === 'loading' && <p role="status">Cargando posiciones…</p>}
      {currentResult.status === 'error' && (
        <div>
          <p role="alert">{currentResult.error}</p>
          <button type="button" className="home-action" onClick={() => setAttempt((value) => value + 1)}>
            Reintentar
          </button>
        </div>
      )}
      {currentResult.status === 'ready' && currentResult.standings.length === 0 && (
        <p role="status">Todavía no hay resultados para mostrar.</p>
      )}
      {currentResult.status === 'ready' && currentResult.standings.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm text-white">
            <thead>
              <tr>
                <th scope="col" className="p-2">Pos.</th>
                <th scope="col" className="p-2">Club</th>
                <th scope="col" className="p-2">PJ</th>
                <th scope="col" className="p-2">PG</th>
                <th scope="col" className="p-2">PE</th>
                <th scope="col" className="p-2">PP</th>
                <th scope="col" className="p-2">GF</th>
                <th scope="col" className="p-2">GC</th>
                <th scope="col" className="p-2">DG</th>
                <th scope="col" className="p-2">Puntos</th>
              </tr>
            </thead>
            <tbody>
              {currentResult.standings.map((standing, index) => (
                <tr key={standing.club_id ?? standing.clubId ?? index} className="border-t border-white/20">
                  <td className="p-2">{index + 1}</td>
                  <th scope="row" className="p-2 font-medium">
                    {standing.club_name ?? standing.clubName}
                  </th>
                  <td className="p-2">{standing.matches_played ?? standing.matchesPlayed}</td>
                  <td className="p-2">{standing.matches_won ?? standing.matchesWon}</td>
                  <td className="p-2">{standing.matches_drawn ?? standing.matchesDrawn}</td>
                  <td className="p-2">{standing.matches_lost ?? standing.matchesLost}</td>
                  <td className="p-2">{standing.goals_for ?? standing.goalsFor}</td>
                  <td className="p-2">{standing.goals_against ?? standing.goalsAgainst}</td>
                  <td className="p-2">{standing.goal_difference ?? standing.goalDifference}</td>
                  <td className="p-2 font-semibold">{standing.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
