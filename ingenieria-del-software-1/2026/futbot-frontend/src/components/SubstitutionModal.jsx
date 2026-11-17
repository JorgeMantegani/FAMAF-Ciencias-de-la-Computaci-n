import { useEffect } from 'react'
import './SubstitutionModal.css'

function PlayerChoice({ player, index, selected, status, onSelect }) {
  return (
    <button
      className={`substitution-player${selected ? ' substitution-player--selected' : ''}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="substitution-player__number">{index + 1}</span>
      <span className="substitution-player__details">
        <strong>{player.name}</strong>
        {selected && <small>{status}</small>}
      </span>
      <span className="substitution-player__radio" aria-hidden="true" />
    </button>
  )
}

export default function SubstitutionModal({
  team_name,
  starters,
  substitutes,
  pending,
  used_this_pause,
  selected_out,
  selected_in,
  submitting,
  error,
  on_select_out,
  on_select_in,
  on_submit,
  on_close,
}) {
  useEffect(() => {
    const close_on_escape = (event) => {
      if (event.key === 'Escape') on_close()
    }
    document.addEventListener('keydown', close_on_escape)
    return () => document.removeEventListener('keydown', close_on_escape)
  }, [on_close])

  const outgoing = starters.find((player) => player.player_id === selected_out)
  const incoming = substitutes.find((player) => player.player_id === selected_in)
  const pending_out = [...starters, ...substitutes].find((player) => player.player_id === pending?.outPlayerId)
  const pending_in = [...starters, ...substitutes].find((player) => player.player_id === pending?.inPlayerId)
  const cannot_submit = used_this_pause || Boolean(pending) || !outgoing || !incoming || submitting

  return (
    <div
      className="substitution-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) on_close()
      }}
    >
      <section
        className="substitution-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="substitution-title"
        aria-describedby="substitution-description"
      >
        <header className="substitution-dialog__header">
          <div className="substitution-dialog__heading">
            <span className="substitution-dialog__icon" aria-hidden="true">↔</span>
            <div>
              <h2 id="substitution-title">Cambios de jugadores</h2>
              <p id="substitution-description">Ajustá tu equipo sin perder de vista el partido.</p>
            </div>
          </div>
          <button className="substitution-back" type="button" onClick={on_close}>← Volver al partido</button>
        </header>

        <div className="substitution-dialog__body">
          {pending && (
            <div className="substitution-scheduled" role="status">
              <strong>Cambio planificado para la próxima pausa:</strong>{' '}
              {pending_out?.name ?? `Jugador ${pending.outPlayerId}`} por {pending_in?.name ?? `Jugador ${pending.inPlayerId}`}
            </div>
          )}

          <p className="substitution-roster-count">{team_name} / {starters.length} titulares + {substitutes.length} suplentes</p>
          <div className="substitution-selection">
            <section className="substitution-list" aria-labelledby="substitution-out-title">
              <div className="substitution-list__heading">
                <span>01</span>
                <div><h3 id="substitution-out-title">Titular que sale</h3><p>Elegí un jugador de la cancha.</p></div>
              </div>
              <div className="substitution-list__options">
                {starters.map((player, index) => (
                  <PlayerChoice
                    key={player.player_id}
                    player={player}
                    index={index}
                    selected={selected_out === player.player_id}
                    status="SALE"
                    onSelect={() => on_select_out(player.player_id)}
                  />
                ))}
                {starters.length === 0 && <p className="substitution-empty">No hay titulares disponibles.</p>}
              </div>
            </section>

            <section className="substitution-list" aria-labelledby="substitution-in-title">
              <div className="substitution-list__heading">
                <span>02</span>
                <div><h3 id="substitution-in-title">Suplente que entra</h3><p>Elegí un jugador del banco.</p></div>
              </div>
              <div className="substitution-list__options">
                {substitutes.map((player, index) => (
                  <PlayerChoice
                    key={player.player_id}
                    player={player}
                    index={index}
                    selected={selected_in === player.player_id}
                    status="ENTRA"
                    onSelect={() => on_select_in(player.player_id)}
                  />
                ))}
                {substitutes.length === 0 && <p className="substitution-empty">No hay suplentes disponibles.</p>}
              </div>
            </section>

            <aside className="substitution-summary" aria-label="Resumen del cambio">
              <div className="substitution-summary__title"><h3>Resumen del cambio</h3><span>{team_name}</span></div>
              <div className="substitution-summary__players">
                <div><span>Sale</span><strong>{outgoing?.name ?? '—'}</strong></div>
                <span className="substitution-summary__arrow" aria-hidden="true">→</span>
                <div><span>Entra</span><strong>{incoming?.name ?? '—'}</strong></div>
              </div>
              {used_this_pause ? (
                <p className="substitution-limit" role="status">Límite alcanzado: 1 cambio por pausa</p>
              ) : pending ? (
                <p className="substitution-summary__status">Cambio en espera de la próxima pausa</p>
              ) : (
                <p className="substitution-summary__status">◉ Listo para confirmar</p>
              )}
            </aside>
          </div>
          {error && <p className="substitution-error" role="alert">{error}</p>}
        </div>

        <footer className="substitution-dialog__footer">
          <p>
            {pending
              ? 'El cambio se aplicará cuando el partido entre en pausa.'
              : 'Un cambio preparado todavía no está aplicado.'}
            <small>{outgoing && incoming ? `Confirmá para reemplazar a ${outgoing.name} por ${incoming.name}.` : 'Seleccioná un titular y un suplente.'}</small>
          </p>
          <div className="substitution-dialog__actions">
            <button className="substitution-cancel" type="button" onClick={on_close}>Cancelar</button>
            <button
              className="substitution-confirm"
              type="button"
              disabled={cannot_submit}
              onClick={on_submit}
            >
              {submitting ? 'Enviando…' : '✓ Confirmar cambio'}
            </button>
          </div>
        </footer>
      </section>
    </div>
  )
}
