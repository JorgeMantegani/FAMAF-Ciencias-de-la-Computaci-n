import { useEffect, useState } from 'react'
import Modal from './modal'

export default function ChangeBehaviorModal({
  starters,
  behaviors,
  on_confirm,
  on_close,
  submitting = false,
}) {
  const [selected_behaviors, set_selected_behaviors] = useState({})

  // Sincronizar selecciones cuando cambia la lista de titulares.
  const starters_signature = JSON.stringify(
    starters.map(({ id, behavior_id }) => [id, behavior_id ?? ''])
  )

  useEffect(() => {
    set_selected_behaviors(
      Object.fromEntries(JSON.parse(starters_signature))
    )
  }, [starters_signature])

  const changes = starters
    .filter(
      (p) =>
        selected_behaviors[p.id] &&
        selected_behaviors[p.id] !== p.behavior_id
    )
    .map((p) => ({
      playerId: p.id,
      behaviorId: selected_behaviors[p.id],
    }))

  return (
    <Modal
      title="Cambiar comportamiento"
      description="Rige desde el próximo tick"
      onClose={submitting ? () => {} : on_close}
    >
      {starters.map((p) => (
        <label key={p.id} className="change-behavior-row">
          {p.name}

          <select
            className="change-behavior-select"
            aria-label={`Comportamiento de ${p.name}`}
            value={selected_behaviors[p.id] ?? ''}
            disabled={submitting}
            onChange={(e) =>
              set_selected_behaviors((current) => ({
                ...current,
                [p.id]: e.target.value,
              }))
            }
          >
            <option value="">Elegir…</option>

            {behaviors.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      ))}

      <div className="change-behavior-actions">
        <button
          type="button"
          className="change-behavior-btn change-behavior-btn--primary"
          disabled={changes.length === 0 || submitting}
          onClick={() => on_confirm(changes)}
        >
          {submitting ? 'Enviando…' : 'Confirmar'}
        </button>

        <button
          type="button"
          className="change-behavior-btn"
          disabled={submitting}
          onClick={on_close}
        >
          Cancelar
        </button>
      </div>
    </Modal>
  )
}
