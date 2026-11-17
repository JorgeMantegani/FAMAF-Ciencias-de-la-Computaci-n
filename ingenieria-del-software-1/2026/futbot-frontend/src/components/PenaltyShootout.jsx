export default function PenaltyShootout({ penalties, home_name, away_name, revision }) {
  if (!penalties.active) return null

  const elapsed_ticks = Number.isInteger(penalties.start_revision)
    ? Math.max(0, revision - penalties.start_revision)
    : 0
  const seconds_remaining = Math.max(0, Math.ceil(
    penalties.max_seconds_per_attempt - elapsed_ticks / penalties.tick_rate,
  ))
  const team_panel = (team, name) => (
    <section className="penalty-team" aria-label={`${name}, tanda de penales`}>
      <h2>{name}</h2>
      <div className="penalty-attempts">
        {Array.from({ length: penalties.max_attempts }, (_, index) => {
          const result = penalties.results[team][index]
          const label = result === 'scored' ? 'gol' : result === 'missed' ? 'fallo' : 'pendiente'
          return (
            <span
              key={index}
              className={`penalty-attempt${result ? ` penalty-attempt--${result}` : ''}`}
              role="img"
              aria-label={`Penal ${index + 1}: ${label}`}
            />
          )
        })}
      </div>
      <p className="penalty-team-score" aria-label={`${name}: ${penalties.scores[team]} goles`}>
        {penalties.scores[team]}
      </p>
    </section>
  )

  return (
    <section className="penalty-shootout" aria-label="Tanda de penales" aria-live="polite">
      <div className="penalty-shootout__header">
        <h2>Tanda de penales</h2>
        {!penalties.completed && (
          <p className="penalty-clock">
            Tiempo del penal: <time aria-label="Tiempo restante del penal">{seconds_remaining}</time> s
          </p>
        )}
      </div>
      <div className="penalty-scoreboard">
        {team_panel('HOME', home_name)}
        <span className="penalty-scoreboard__separator" aria-hidden="true">–</span>
        {team_panel('AWAY', away_name)}
      </div>
      {penalties.completed && (
        <p className="penalty-winner">
          {penalties.winner
            ? `Ganador de la tanda: ${penalties.winner === 'HOME' ? home_name : away_name}`
            : 'Tanda finalizada'}
        </p>
      )}
    </section>
  )
}
