import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { join_friendly_room, list_behaviors, list_players } from '../api/client'
import { read_session } from '../auth/session'
import SquadSelector from '../components/SquadSelector'
import { empty_squad, is_squad_complete } from '../components/squad'
import MiniPitchViewer from '../components/mini_pitch_viewer'
import './Home.css'
import './join_friendly.css'

const EMPTY_SQUAD = () => ({
  starters: Array.from({ length: 3 }, () => ({ playerId: '', behaviorId: '' })),
  substitutes: Array.from({ length: 3 }, () => ({ playerId: '', behaviorId: '' })),
})

const all_slots = (team) => [...team.starters, ...team.substitutes]

const has_selection = (team) =>
  all_slots(team).some((slot) => slot.playerId !== '' || slot.behaviorId !== '')

const to_selection = (slot) => ({ player_id: String(slot.playerId), behavior_id: String(slot.behaviorId) })

// Ventana de aviso. Se cierra usando las acciones que muestra el aviso.
function NoticeDialog({ notice, children }) {
  const dialog_ref = useRef(null)

  useEffect(() => {
    const dialog = dialog_ref.current
    if (!dialog) return
    if (notice && !dialog.open) dialog.showModal()
    else if (!notice && dialog.open) dialog.close()
  }, [notice])

  return (
    <dialog ref={dialog_ref} className="join-notice" onCancel={(event) => event.preventDefault()}>
      {notice && (
        <>
          <h2>{notice.title}</h2>
          <p role="alert">{notice.message}</p>
          <div className="join-actions">{children}</div>
        </>
      )}
    </dialog>
  )
}

export default function JoinFriendly() {
  const navigate = useNavigate()
  const location = useLocation()

  // La sala llega desde el listado público; si se abre la pantalla sin sala, vuelve al listado
  const room_id = location.state?.room_id ?? null
  const home_club_name = location.state?.home_club_name ?? ''
  const has_room = Boolean(room_id)

  // La plantilla puede venir de un intento anterior (sala ocupada): no se pierde
  const [squad, set_squad] = useState(() => location.state?.squad ?? EMPTY_SQUAD())
  const [players, set_players] = useState([])
  const [behaviors, set_behaviors] = useState([])
  const [load_status, set_load_status] = useState('loading')
  const [load_error, set_load_error] = useState('')
  const [attempt, set_attempt] = useState(0)
  const [submitting, set_submitting] = useState(false)
  const [notice, set_notice] = useState(null)
  const [change_open, set_change_open] = useState(false)
  const [preview_selection, set_preview_selection] = useState(null)

  useEffect(() => {
    if (!read_session()) {
      navigate('/login', { replace: true })
      return
    }
    if (!has_room) {
      navigate('/friendly', { replace: true })
      return
    }
    const unauthorized = () => navigate('/login', { replace: true })
    window.addEventListener('futbot:unauthorized', unauthorized)
    return () => window.removeEventListener('futbot:unauthorized', unauthorized)
  }, [navigate, has_room])

  // Carga jugadores y comportamientos
  useEffect(() => {
    if (!has_room) return
    const controller = new AbortController()

    Promise.all([
      list_players({ signal: controller.signal }),
      list_behaviors({ signal: controller.signal }),
    ])
      .then(([loaded_players, loaded_behaviors]) => {
        if (controller.signal.aborted) return
        set_players(loaded_players)
        set_behaviors(loaded_behaviors)
        set_load_status('ready')
      })
      .catch((cause) => {
        if (controller.signal.aborted || cause.name === 'AbortError') return
        set_load_error(cause.message || 'No se pudieron cargar tus jugadores y comportamientos.')
        set_load_status('error')
      })

    return () => controller.abort()
  }, [attempt, has_room])

  if (!has_room) return null

  const is_complete = is_squad_complete(squad)

  // Vuelve al listado llevándose la plantilla, para usarla en otra sala
  function back_to_list() {
    set_notice(null)
    navigate('/friendly', { state: has_selection(squad) ? { squad } : null })
  }

  function handle_join_error(cause) {
    const message = cause.message || 'Ocurrió un error inesperado.'

    if (cause.status === 401) {
      set_notice({ kind: 'other', title: 'Sesión vencida', message: 'Tu sesión no es válida o venció. Iniciá sesión nuevamente.' })
      return
    }

    // 409: otro club ocupó el cupo visitante antes. 404: la sala ya no existe.
    // En ambos casos la plantilla no se toca: se puede usar en otra sala.
    if (cause.status === 409 || cause.status === 404) {
      set_notice({
        kind: 'unavailable',
        title: 'La sala ya no está disponible',
        message: 'Otro club se unió antes que vos o la sala se cerró. Volvé al listado y elegí otra: tu plantilla se conserva.',
      })
      return
    }

    if (cause.error_code === 'INVALID_SQUAD' || (cause.status === 400 && /jugador|comportamiento|selecci[oó]n|plantilla/i.test(message))) {
      set_notice({ kind: 'invalid_selection', title: 'Selección no válida', message: `${message} Revisá los seis puestos y sus comportamientos.` })
      return
    }

    if (cause.status === 422) {
      set_notice({ kind: 'other', title: 'Datos no válidos', message: `El servidor rechazó los datos enviados: ${message}` })
      return
    }

    set_notice({
      kind: 'other',
      title: 'No se pudo unir al amistoso',
      message: cause.status
        ? `Error HTTP ${cause.status}: ${message}`
        : 'No se pudo conectar con el servidor. Verificá tu conexión e intentá nuevamente.',
    })
  }
  
  function handle_preview(slot) {
    set_preview_selection({
      player_id: slot.playerId,
      behavior_id: slot.behaviorId,
    })
  }

  async function confirm() {
    if (!is_complete || submitting) return
    set_submitting(true)
    try {
      await join_friendly_room({
        room_id,
        starters: squad.starters.map(to_selection),
        substitutes: squad.substitutes.map(to_selection),
      })
      navigate(`/amistosos/${room_id}/sala`, { replace: true })
    } catch (cause) {
      if (cause.name !== 'AbortError') handle_join_error(cause)
    } finally {
      set_submitting(false)
    }
  }

  function retry_selection() {
    set_notice(null)
    set_squad(EMPTY_SQUAD())
  }

  function retry_load() {
    set_load_error('')
    set_load_status('loading')
    set_attempt((current) => current + 1)
  }

  return (
    <div className="home-page">
      {preview_selection && (
      <MiniPitchViewer
        player_id={preview_selection.player_id}
        behavior_id={preview_selection.behavior_id}
        onClose={() => set_preview_selection(null)}
      />
      )}
      <main className="home-content">
        <section className="home-welcome" aria-labelledby="join-title">
          <h1 id="join-title">Unirse a amistoso</h1>
          <p>{home_club_name ? `Sala de ${home_club_name}` : `Sala: ${room_id}`}</p>
          <div className="join-row">
            <button className="home-action" onClick={back_to_list}>Volver</button>
          </div>
        </section>

        {load_status === 'loading' && (
          <div className="home-notice" role="status">Cargando tus jugadores y comportamientos…</div>
        )}

        {load_status === 'error' && (
          <>
            <p className="home-notice home-error" role="alert">{load_error}</p>
            <button className="home-action" onClick={retry_load}>Reintentar</button>
          </>
        )}

        {load_status === 'ready' && (
          <>
            {players.length < 6 && (
              <p className="home-notice" role="alert">
                Tenés {players.length} jugadores. Necesitás al menos 6 jugadores distintos para completar titulares y suplentes.
              </p>
            )}

            {behaviors.length === 0 && (
              <p className="home-notice" role="alert">
                No hay comportamientos disponibles. No vas a poder confirmar hasta que el servidor devuelva al menos uno.
              </p>
            )}

            <section className="join-panel" aria-labelledby="join-team-title">
              <h2 id="join-team-title">Elegí tu equipo</h2>
              <p>
                Seleccioná 3 titulares y 3 suplentes. Cada puesto necesita un jugador y un comportamiento.
                Un jugador no puede ocupar dos puestos.
              </p>

              <SquadSelector
                players={players}
                behaviors={behaviors}
                squad={squad}
                setSquad={set_squad}
                onPreview={handle_preview}
              />
            </section>

            <div className="join-row">
              <button className="home-action" onClick={confirm} disabled={!is_complete || submitting}>
                {submitting ? 'Uniéndote…' : 'Confirmar y unirse'}
              </button>
              {!is_complete && (
                <p className="join-hint" role="status">
                  Completá los seis puestos con jugadores distintos y asignales un comportamiento.
                </p>
              )}
            </div>
          </>
        )}
      </main>

      <NoticeDialog notice={notice}>
        {notice?.kind === 'unavailable' && (
          <button className="home-action" onClick={back_to_list}>Volver al listado</button>
        )}
        {notice?.kind === 'invalid_selection' && (
          <button className="home-action" onClick={retry_selection}>Volver a seleccionar</button>
        )}
        {notice?.kind === 'other' && (
          <button className="home-action" onClick={() => set_notice(null)}>Cerrar</button>
        )}
      </NoticeDialog>
    </div>
  )
}