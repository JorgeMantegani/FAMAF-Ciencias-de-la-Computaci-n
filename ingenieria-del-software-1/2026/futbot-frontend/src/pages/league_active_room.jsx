import { useParams, useNavigate } from 'react-router-dom';
import { read_session } from '../auth/session';
import { useLeagueLobbySocket } from '../hooks/use_league_live_socket';
import ChangeLineupModal from '../components/change_lineup_modal';
import './league_active_room.css'
import {useState} from "react";

export default function OngoingLeagueLobbyView() {
    const { league_id } = useParams();
    const navigate = useNavigate();
    const session = read_session();
    const token = session?.access_token ?? session?.token;
    const user_club_id = session?.club_id;
    const [lineup_open, set_lineup_open] = useState(false)
    const [lineup_notice, set_lineup_notice] = useState(null)

    const { lobby_data, loading, error, last_toast } = useLeagueLobbySocket(league_id, token);
    const { league_name, status, currentMatch, nextMatch, standings, calendar } = lobby_data || {};

    const my_squad = lobby_data?.my_squad ?? []
    const can_change_lineup =
      status === 'in_progress' &&
      my_squad.length === 6 &&
      my_squad.every((player) => player.player_id)

    if (loading && !lobby_data) {
        return (
            <div className="lobby-view">
                <div className="lobby-header skeleton" style={{ height: '80px' }} />
                <div className="lobby-grid">
                    <div className="match-card skeleton" style={{ height: '200px' }} />
                    <div className="match-card skeleton" style={{ height: '200px' }} />
                </div>
            </div>
        );
    }

    if (error) {
        return <div className="waiting-error">Error al cargar la liga: {error}</div>;
    }

    
    return (
        <div className="lobby-view">
            {/* Toast sutil de notificación en tiempo real */}
            {last_toast && (
                <div className="toast-alert" role="status">
                    ⚽ {last_toast}
                </div>
            )}

            <header className="lobby-header">
                <div>
                    <h1 className="text-xl font-bold">{league_name || 'Lobby de Liga'}</h1>
                    <p className="text-sm text-[#b5c2b3]">Estado: <span className="uppercase text-[#bf9548] font-semibold">{status}</span></p>
                </div>
                {can_change_lineup && (
                    <button
                      className="waiting-btn-primary"
                      onClick={() => set_lineup_open(true)}
                    >
                      Cambiar alineación
                    </button>
                )}
                <button className="waiting-btn-secondary" onClick={() => navigate('/home')}>
                    Volver al Home
                </button>
            </header>

            {/* Aviso especial si la liga ha finalizado */}
            {status === 'finished' && (
                <div className="bg-[#164e2c] border border-[#2f5a36] p-4 rounded-md text-center text-white my-4">
                    <h2 className="text-lg font-bold text-[#bf9548]">🏆 ¡El torneo ha finalizado!</h2>
                    <p className="text-sm text-[#b5c2b3] mt-1">Consulta la tabla de posiciones definitiva y el historial completo del calendario.</p>
                </div>
            )}
            
            <div className="lobby-grid">
                {/* Partido en Disputa */}
                <section className="match-card">
                    <h2 className="text-lg font-semibold border-b border-[#2f5a36] pb-2">Partido en Vivo (Current Match)</h2>
                    {currentMatch ? (
                        <div className="flex flex-col gap-3 py-4 items-center text-center">
                            <p className="text-sm text-[#c9d6c5]">Jornada {currentMatch.round}</p>
                            <div className="flex justify-between items-center w-full px-6">
                                <span className="font-bold text-lg">{currentMatch.home_club_name || 'Local'}</span>
                                <span className="text-2xl font-mono bg-[#0b2a16] px-4 py-1 rounded border border-[#2f5a36]">
                                    {currentMatch.home_score} - {currentMatch.away_score}
                                </span>
                                <span className="font-bold text-lg">{currentMatch.away_club_name || 'Visitante'}</span>
                            </div>
                            <button 
                                className="waiting-btn-primary mt-2 text-xs py-2 px-4"
                                onClick={() => navigate(`/matches/${currentMatch.id}`)}
                            >
                                Ver Transmisión en Vivo 👁️
                            </button>
                        </div>
                    ) : (
                        <p className="text-sm text-[#c9d6c5] italic py-6 text-center">No hay ningún partido disputándose en este momento exacto.</p>
                    )}
                </section>

                {/* Siguiente Partido / Preview */}
                <section className="match-card">
                    <h2 className="text-lg font-semibold border-b border-[#2f5a36] pb-2">Próximo Encuentro (Next Match)</h2>
                    {nextMatch ? (
                        <div className="flex flex-col gap-3 py-4 items-center text-center">
                            <p className="text-sm text-[#c9d6c5]">Jornada {nextMatch.round}</p>
                            <div className="flex justify-between items-center w-full px-6">
                                <span className="font-medium">{nextMatch.home_club_name || 'Local'}</span>
                                <span className="text-sm font-mono uppercase text-[#bf9548]">VS</span>
                                <span className="font-medium">{nextMatch.away_club_name || 'Visitante'}</span>
                            </div>
                            <p className="text-xs text-[#b5c2b3] mt-2">Prepárate en tu plantilla y tácticas.</p>
                        </div>
                    ) : (
                        <p className="text-sm text-[#c9d6c5] italic py-6 text-center">No hay más partidos programados próximamente.</p>
                    )}
                </section>
            </div>

            {/* Tabla de Clasificación */}
            <section className="standings-card">
                <h2 className="text-lg font-semibold border-b border-[#2f5a36] pb-2">Tabla de Clasificación</h2>
                <div className="overflow-x-auto">
                    <table className="standings-table">
                        <thead>
                            <tr className="text-[#b5c2b3] text-xs uppercase border-b border-[#2f5a36]">
                                <th>Pos</th>
                                <th>Club</th>
                                <th>PTS</th>
                                <th>PJ</th>
                                <th>G</th>
                                <th>E</th>
                                <th>P</th>
                                <th>GF</th>
                                <th>GC</th>
                                <th>DG</th>
                            </tr>
                        </thead>
                        <tbody>
                            {standings?.map((row, index) => {
                                const is_my_club = row.club_id === user_club_id;
                                return (
                                    <tr key={row.club_id} className={is_my_club ? 'my-club-row' : ''}>
                                        <td>{index + 1}</td>
                                        <td className="font-medium">{row.club_name} {is_my_club && '(Tú)'}</td>
                                        <td className="font-bold">{row.points}</td>
                                        <td>{row.matches_played}</td>
                                        <td>{row.matches_won}</td>
                                        <td>{row.matches_drawn}</td>
                                        <td>{row.matches_lost}</td>
                                        <td>{row.goals_for}</td>
                                        <td>{row.goals_against}</td>
                                        <td>{row.goal_difference}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </section>
            {/* Modal para cambiar alineación */}
            {lineup_notice && (
              <div role="status" className="toast-alert">
                {lineup_notice}
              </div>
            )}
            {lineup_open && (
              <ChangeLineupModal
                league_id={league_id}
                squad={my_squad}
                onClose={() => set_lineup_open(false)}
                onSuccess={(message) => {
                  set_lineup_notice(message)
                  window.setTimeout(() => set_lineup_notice(null), 5000)
                }}
              />
            )}

            {/* Calendario / Fixture */}
            <section className="calendar-card">
                <h2 className="text-lg font-semibold border-b border-[#2f5a36] pb-2">Calendario del Torneo</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-60 overflow-y-auto pr-2">
                    {calendar?.map((match) => (
                        <div key={match.id} className="flex justify-between items-center p-3 bg-[#0b2a16] rounded border border-[#2f5a36] text-sm">
                            <span className="text-xs text-[#b5c2b3]">J{match.round}</span>
                            <span className="truncate max-w-[120px]">{match.home_club_name}</span>
                            <span className="font-mono font-bold bg-[#164e2c] px-2 py-0.5 rounded">
                                {match.status === 'finished' ? `${match.home_score} - ${match.away_score}` : 'vs'}
                            </span>
                            <span className="truncate max-w-[120px] text-right">{match.away_club_name}</span>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}
