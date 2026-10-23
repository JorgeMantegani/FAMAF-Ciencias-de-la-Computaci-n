// Provisional field size: the API documents a centered origin but no dimensions.
// Keep the conversion here until the engine's field dimensions are confirmed.
const FIELD_WIDTH = 100
const FIELD_HEIGHT = 60
const project = ({ x, y }) => ({
  x: 648 + Math.max(-0.5, Math.min(0.5, x / FIELD_WIDTH)) * 1160,
  y: 311 - Math.max(-0.5, Math.min(0.5, y / FIELD_HEIGHT)) * 554,
})

export default function MatchPitch({ state, protocol_state }) {
  const players = state.players.length ? state.players : Object.values(protocol_state?.players ?? {}).map((player) => ({
    player_id: player.id,
    club_id: player.club_id,
    name: player.name ?? `Jugador ${player.id}`,
    on_field: player.is_playing,
    has_ball: false,
    position: { x: player.x, y: player.y },
  }))
  const ball = state.ball ?? protocol_state?.ball
  return (
    <svg className="match-pitch" viewBox="0 0 1296 622" role="img" aria-label="Cancha del partido con las posiciones de los jugadores y la pelota">
      <g className="match-pitch-stripes" aria-hidden="true">
        {[0, 324, 648, 972].map((x) => <rect key={x} x={x} width="162" height="622" />)}
      </g>
      <g className="match-pitch-lines" aria-hidden="true">
        <rect className="match-pitch-goal" x="28" y="233" width="40" height="156" rx="8" />
        <rect className="match-pitch-goal" x="1228" y="233" width="40" height="156" rx="8" />
        <path d="M68 34H1228V588H68Z M648 34V588 M68 160H252V462H68 M1228 160H1044V462H1228 M68 230H140V392H68 M1228 230H1156V392H1228" />
        <circle cx="648" cy="311" r="69" />
        <circle className="match-pitch-center" cx="648" cy="311" r="5" />
      </g>
      {players.filter((player) => player.on_field && player.position).map((player) => {
        const point = project(player.position)
        const home = player.club_id === state.home_club.club_id
        const number = players.filter((item) => item.club_id === player.club_id).findIndex((item) => item.player_id === player.player_id) + 1
        return (
          <g key={player.player_id} className={`match-pitch-player match-pitch-player--${home ? 'home' : 'away'}`} transform={`translate(${point.x} ${point.y})`}>
            <title>{player.name} · {home ? state.home_club.name : state.away_club.name}{player.has_ball ? ' · Con pelota' : ''}</title>
            {player.has_ball && <circle className="match-possession-ring" r="30" />}
            <circle r="24" />
            <text textAnchor="middle" dy=".35em">{number}</text>
          </g>
        )
      })}
      {ball && <g className="match-pitch-ball" transform={`translate(${project(ball).x} ${project(ball).y})`}><title>Pelota</title><circle r="9" /><path d="m0-4 4 3-2 5h-4l-2-5Z" /></g>}
    </svg>
  )
}
