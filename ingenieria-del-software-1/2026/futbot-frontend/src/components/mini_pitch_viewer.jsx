import MatchPitch from './match_pitch'
import '../pages/Match.css'
import './mini_pitch_viewer.css'

import { useBehaviorSimulation } from '../hooks/use_behavior_simulation'

const SIMULATION_FIELD_LENGTH = 105
const SIMULATION_FIELD_WIDTH = 68

function normalize_simulation_position(position) {
  if (!position) return null

  return {
    x: (position.x / SIMULATION_FIELD_LENGTH - 0.5) * 100,
    y: (position.y / SIMULATION_FIELD_WIDTH - 0.5) * 60,
  }
}


function to_pitch_state(tick, player_id) {
  // Sino hay tick o no hay jugadores devuelvo null para que el componente no intente renderizar nada
  if (!tick || !tick.players) return null;

  const players = tick.players.map((player) => ({
    player_id: String(player.id),
    club_id: player.team === 'HOME' ? 'home' : 'away',
    name: String(player.id) === String(player_id) 
      ? 'Jugador seleccionado' 
      : 'Rival estatico',
    is_selected: String(player.id) === String(player_id),
    on_field: true,
    has_ball: String(player.id) === String(tick.ball?.owner_id),
    position: normalize_simulation_position(player.position),
  }))
  return {
    'home_club': { club_id: 'home', name: 'Equipo local' },
    'away_club': { club_id: 'away', name: 'Equipo visitante' },
    'players': players,
    'ball': normalize_simulation_position(tick.ball?.position),
  }
}

export default function MiniPitchViewer({ player_id, behavior_id, onClose }) {
  const { simulationData, connectionStatus, error } = useBehaviorSimulation(player_id, behavior_id)
  const is_loading = connectionStatus === 'connecting' && !simulationData
  const pitch_state = simulationData?.type === 'tick' ? to_pitch_state(simulationData, player_id) : null;

  return (
  <div className="mini-pitch-viewer"  onClick={(event) => event.stopPropagation()}>
    <div className="mini-pitch-viewer__panel">
      <div className="mini-pitch-viewer__header">
        <div>
          <h3>Prueba de comportamiento</h3>
          <p>Estado: {connectionStatus}</p>
        </div>

        <button 
          type="button" 
          className="mini-pitch-viewer__close"
          onClick={onClose}>
          Cerrar prueba
        </button>
      </div>

      {error && (
        <p role="alert">
          {typeof error === 'string'
            ? error
            : 'Error en la simulación'}
        </p>
      )}

      {is_loading && !error && (
        <p role="status">
          Conectando con la simulación…
        </p>
      )}

      {connectionStatus === 'offline' && !simulationData && !error && (
        <p role="alert">
          La simulación se desconectó antes de enviar datos.
        </p>
      )}

      {pitch_state && (
        <div className="mini-pitch-viewer__pitch">
          <MatchPitch state={pitch_state} />
        </div>
      )}
    </div>
  </div>
  )
}
