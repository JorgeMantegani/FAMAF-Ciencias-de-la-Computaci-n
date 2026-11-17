import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { read_session } from "../auth/session";
import { use_league_waiting_socket } from "../hooks/use_league_waiting_socket";
import './league_waiting_room.css';

export default function LeagueWaitingRoom() {
    const { league_id } = useParams();
    const navigate = useNavigate();
    const [club_id, set_club_id] = useState(null);

    useEffect(() => {
        const session = read_session();
        if (!session || !session.club_id) {
            navigate('/login', { replace: true});
            return;
        }
        set_club_id(session.club_id);
    }, [navigate]);

    const { room_info, error, redirect_url, send_action } = use_league_waiting_socket(league_id, club_id);

    useEffect(() => {
        if (redirect_url) {
            navigate(redirect_url);
        }
    }, [redirect_url, navigate]);

    if (!room_info && !error) {
        return <div className="waiting-container"><div className="waiting-notice">Conectando al lobby de la liga...</div></div>;
    }

    const is_creator = room_info?.creator_club_id === club_id;
    const min_clubs = room_info?.min_clubs || 0;
    const current_participants = room_info?.current_participants || 0;
    const missing_participants = Math.max(0, min_clubs - current_participants);
    const can_start = room_info?.current_participants >= room_info?.min_clubs;

    return (
        <div className="waiting-page">
          <header className="waiting-topbar">
            <h1>Lobby de Espera: {room_info?.league_name || 'Cargando...'}</h1>
            <button className="waiting-btn-secondary" onClick={() => navigate('/home')}>
              Salir al Home
            </button>
          </header>

          <main className="waiting-content">
            {error && <div className="waiting-error" role="alert">{error}</div>}

            <section className="waiting-card info-card">
              <h2>Información de la Liga</h2>
              <p><strong>Creador:</strong> {room_info?.creator_club_name} {is_creator && '(Tú)'}</p>
              <p><strong>Participantes actual:</strong> {room_info?.current_participants} / {room_info?.max_clubs}</p>
              <p><strong>Mínimo requerido para iniciar:</strong> {room_info?.min_clubs}</p>
          
              <div className={`status-badge ${can_start ? 'ready' : 'waiting'}`}>
                {can_start 
                  ? '¡Se alcanzó el mínimo necesario para iniciar!' 
                  : `Esperando más participantes (Faltan al menos ${missing_participants})`}
              </div>
            </section>

            <section className="waiting-card participants-card">
              <h2>Clubes Inscriptos</h2>
              <ul className="participants-list">
                {room_info?.inscribed_clubs?.map((id) => (
                  <li key={id} className={`participant-item ${id === room_info?.creator_club_id ? 'creator-item' : ''}`}>
                    <span>{id === club_id ? 'Mi Club' : `Club ID: ${id.slice(0, 8)}...`}</span>
                    {id === room_info?.creator_club_id && <span className="creator-tag">Creador</span>}
                  </li>
                ))}
              </ul>
            </section>

            {is_creator ? (
              <div className="creator-actions">
                <button 
                  className="waiting-btn-primary" 
                  disabled={!can_start} 
                  onClick={() => send_action('start_league')}
                >
                  Iniciar Liga
                </button>
                <button 
                  className="waiting-btn-danger" 
                  onClick={() => send_action('cancel_league')}
                >
                  Cancelar Liga
                </button>
              </div>
            ) : (
              <div className="creator-actions">
                <div className="waiting-notice-card">
                  <p>Esperando a que el creador de la sala dé inicio a la liga...</p>
                </div>
                <button
                  className="waiting-btn-danger"
                  onClick={() => send_action('leave_room')}
                  >
                    Abandonar Liga
                  </button>
              </div>
            )}
          </main>
        </div>
  );
}