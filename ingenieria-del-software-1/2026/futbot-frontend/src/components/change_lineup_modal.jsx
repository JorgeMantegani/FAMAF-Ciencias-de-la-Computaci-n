import { useState } from 'react'
import { update_league_lineup } from '../api/leagues'
import './change_lineup_modal.css'

const MAX_PLAYERS = 3

export default function ChangeLineupModal({ league_id, squad, onClose, onSuccess }) {
  const [starters, set_starters] = useState(
    squad.filter((player) => player.role === 'starter')
  )
  const [substitutes, set_substitutes] = useState(
    squad.filter((player) => player.role === 'substitute')
  )
  const [saving, set_saving] = useState(false)
  const [error, set_error] = useState(null)

  const is_valid = starters.length === 3 && substitutes.length === 3

  function move_to_substitutes(player) {
    set_starters((current) =>
      current.filter((item) => item.player_id !== player.player_id)
    )
    set_substitutes((current) => [...current, player])
  }

  function move_to_starters(player) {
    set_substitutes((current) =>
      current.filter((item) => item.player_id !== player.player_id)
    )
    set_starters((current) => [...current, player])
  }

  async function handle_submit(event) {
    event.preventDefault()
    if (!is_valid || saving) return

    set_saving(true)
    set_error(null)

    try {
      await update_league_lineup(league_id, {
        starters: starters.map((player) => player.player_id),
        substitutes: substitutes.map((player) => player.player_id),
      })

      onSuccess(
        'Alineación actualizada. Se implementará a partir de tu siguiente partido'
      )
      onClose()
    } catch (request_error) {
      set_error(request_error.message)
    } finally {
      set_saving(false)
    }
  }

  return (
    <div className="lineup-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="lineup-title">
      <div className="lineup-modal">
        <div className="lineup-modal-header">
          <h2 id="lineup-title">Cambiar Alineación</h2>
          <button type="button" className="btn-close-x" onClick={onClose} aria-label="Cerrar modal">
            ✕
          </button>
        </div>

        <form onSubmit={handle_submit} className="lineup-modal-form">
          {/* Sección Titulares */}
          <div className="lineup-section">
            <div className="lineup-section-header">
              <h3>Titulares</h3>
              <span className={`counter-badge ${starters.length === 3 ? 'valid' : 'invalid'}`}>
                {starters.length}/3
              </span>
            </div>
            <div className="player-list">
              {starters.map((player) => (
                <div key={player.player_id} className="player-card starter">
                  <span className="player-name">{player.name}</span>
                  <button
                    type="button"
                    className="btn-move to-sub"
                    onClick={() => move_to_substitutes(player)}
                    aria-label={`Mover ${player.name} a suplentes`}
                    title="Pasar a Suplentes"
                  >
                    ↓ Suplente
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Sección Suplentes */}
          <div className="lineup-section">
            <div className="lineup-section-header">
              <h3>Suplentes</h3>
              <span className={`counter-badge ${substitutes.length === 3 ? 'valid' : 'invalid'}`}>
                {substitutes.length}/3
              </span>
            </div>
            <div className="player-list">
              {substitutes.map((player) => (
                <div key={player.player_id} className="player-card substitute">
                  <span className="player-name">{player.name}</span>
                  <button
                    type="button"
                    className="btn-move to-starter"
                    onClick={() => move_to_starters(player)}
                    aria-label={`Mover ${player.name} a titulares`}
                    title="Pasar a Titulares"
                  >
                    ↑ Titular
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Mensajes de Estado */}
          {!is_valid && (
            <p className="lineup-alert warning" role="alert">
              ⚠️ Debes seleccionar exactamente 3 titulares y 3 suplentes.
            </p>
          )}

          {error && (
            <p className="lineup-alert error" role="alert">
              {error}
            </p>
          )}

          <p className="lineup-notice">
            💡 El cambio regirá desde tu próximo partido.
          </p>

          {/* Botones de Acción */}
          <div className="lineup-modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={!is_valid || saving}>
              {saving ? 'Guardando...' : 'Confirmar alineación'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
