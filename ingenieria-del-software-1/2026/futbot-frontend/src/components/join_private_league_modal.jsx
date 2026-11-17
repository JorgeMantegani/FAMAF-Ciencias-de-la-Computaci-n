import { useEffect, useRef, useState } from 'react'
import { find_league_by_code } from '../api/leagues'
import './join_friendly_modal.css'

const NOT_FOUND_MESSAGE = 'No hay ninguna liga con ese código. Revisalo e intentá de nuevo.'

// A value like ".." would change the request path.
const CODE_CHARACTERS = /^[a-z0-9]+$/i

function search_error(cause) {
  if (!cause.status) return 'No se pudo contactar al servidor.'
  if (cause.error_code === 'LEAGUE_NOT_FOUND') return NOT_FOUND_MESSAGE
  return 'No se pudo buscar la liga. Intentá nuevamente.'
}

export default function JoinPrivateLeagueModal({ on_close, on_found }) {
  const dialog_ref = useRef(null)
  const search_ref = useRef(null)
  const [code, set_code] = useState('')
  const [error, set_error] = useState('')
  const [searching, set_searching] = useState(false)

  useEffect(() => {
    if (!dialog_ref.current.open) dialog_ref.current.showModal()
    return () => search_ref.current?.abort()
  }, [])

  async function submit(event) {
    event.preventDefault()
    if (searching) return

    const clean_code = code.trim()
    if (!clean_code) {
      set_error('Ingresá el código de la liga.')
      return
    }
    if (!CODE_CHARACTERS.test(clean_code)) {
      set_error(NOT_FOUND_MESSAGE)
      return
    }

    const controller = new AbortController()
    search_ref.current = controller
    set_error('')
    set_searching(true)

    try {
      const league = await find_league_by_code(clean_code, { signal: controller.signal })
      if (!controller.signal.aborted) on_found(league)
    } catch (cause) {
      if (controller.signal.aborted || cause.name === 'AbortError' || cause.status === 401) return
      set_error(search_error(cause))
    } finally {
      set_searching(false)
    }
  }

  return (
    <dialog
      ref={dialog_ref}
      className="join-modal"
      aria-labelledby="join-private-league-title"
      onClose={on_close}
      onClick={(event) => { if (event.target === dialog_ref.current) on_close() }}
    >
      <form onSubmit={submit}>
        <h2 id="join-private-league-title">Unirse a liga privada</h2>
        <p>Ingresá el código que te compartió quien creó la liga.</p>

        <label htmlFor="join-league-code">Código de la liga</label>
        <input
          id="join-league-code"
          value={code}
          onChange={(event) => set_code(event.target.value)}
          placeholder="a1b2c3d4"
          autoComplete="off"
          readOnly={searching}
        />

        {error && <p className="join-modal-error" role="alert">{error}</p>}

        <div className="join-modal-actions">
          <button type="button" className="home-action" onClick={on_close}>Cancelar</button>
          <button type="submit" className="home-action" disabled={searching}>
            {searching ? 'Buscando…' : 'Buscar liga'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
