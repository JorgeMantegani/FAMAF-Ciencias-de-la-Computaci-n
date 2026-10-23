import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  join_friendly_room,
  list_behaviors,
  list_players,
} from '../api/client'
import { read_session } from '../auth/session'
import JoinFriendlyModal from '../components/join_friendly_modal'
import SquadSelector from '../components/SquadSelector'
import './Home.css'
import './join_friendly.css'

const EMPTY_SQUAD = () => ({
  starters: Array.from({ length: 3 }, () => ({
    playerId: '',
    behaviorId: '',
  })),
  substitutes: Array.from({ length: 3 }, () => ({
    playerId: '',
    behaviorId: '',
  })),
})

const ERROR_MESSAGES = {
  UNAUTHORIZED: 'Tu sesión no es válida o venció. Iniciá sesión nuevamente.',
  ROOM_NOT_FOUND: 'La sala no existe o el ID no es válido.',
  MATCH_ALREADY_STARTED: 'El partido ya fue iniciado y no admite nuevos participantes.',
  INVALID_SQUAD:
    'La selección de jugadores o comportamientos no es válida. Revisá los seis puestos.',
  ROOM_NOT_FULL: 'La sala todavía no está completa para iniciar el partido.',
  ROOM_NOT_READY: 'La sala no está en condiciones de iniciar el partido.',
  NOT_ROOM_MEMBER: 'Tu club no pertenece a esta sala.',
}

// Ventana de aviso. Se cierra usando las acciones que muestra el aviso.
function NoticeDialog({ notice, children }) {
  const dialog_ref = useRef(null)

  useEffect(() => {
    const dialog = dialog_ref.current
    if (!dialog) return

    if (notice && !dialog.open) {
      dialog.showModal()
    } else if (!notice && dialog.open) {
      dialog.close()
    }
  }, [notice])

  return (
    <dialog
      ref={dialog_ref}
      className="join-notice"
      onCancel={(event) => event.preventDefault()}
    >
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

  const [room, set_room] = useState(() =>
    location.state?.room_id
      ? {
          room_id: location.state.room_id,
          code: location.state.code,
        }
      : null
  )

  const has_room = Boolean(room)

  const [players, set_players] = useState([])
  const [behaviors, set_behaviors] = useState([])
  const [squad, set_squad] = useState(EMPTY_SQUAD)
  const [load_status, set_load_status] = useState('loading')
  const [load_error, set_load_error] = useState('')
  const [attempt, set_attempt] = useState(0)
  const [submitting, set_submitting] = useState(false)
  const [notice, set_notice] = useState(null)
  const [change_open, set_change_open] = useState(false)

  // Verifica sesión y existencia de la sala recibida desde Home.
  useEffect(() => {
    if (!read_session()) {
      navigate('/login', { replace: true })
      return
    }

    if (!has_room) {
      navigate('/home', { replace: true })
      return
    }

    const unauthorized = () => {
      navigate('/login', { replace: true })
    }

    window.addEventListener('futbot:unauthorized', unauthorized)

    return () => {
      window.removeEventListener('futbot:unauthorized', unauthorized)
    }
  }, [navigate, has_room])

  // Carga jugadores y comportamientos. AbortController evita actualizar
  // el estado si el usuario sale de la pantalla durante la petición.
  useEffect(() => {
    if (!has_room) return

    const controller = new AbortController()

    async function load_data() {
      set_load_status('loading')
      set_load_error('')

      try {
        const [loaded_players, loaded_behaviors] = await Promise.all([
          list_players({ signal: controller.signal }),
          list_behaviors({ signal: controller.signal }),
        ])

        if (controller.signal.aborted) return

        set_players(loaded_players)
        set_behaviors(loaded_behaviors)
        set_load_status('ready')
      } catch (cause) {
        if (controller.signal.aborted || cause.name === 'AbortError') {
          return
        }

        set_load_error(
          cause.message || 'No se pudieron cargar tus jugadores y comportamientos.'
        )
        set_load_status('error')
      }
    }

    load_data()

    return () => controller.abort()
  }, [attempt, has_room])

  if (!room) return null

  const is_squad_complete = (team) => {
    const all_slots = [...team.starters, ...team.substitutes]

    return (
      all_slots.length === 6 &&
      all_slots.every(
        (slot) =>
          slot.playerId !== '' &&
          slot.playerId != null &&
          slot.behaviorId !== '' &&
          slot.behaviorId != null
      ) &&
      new Set(all_slots.map((slot) => String(slot.playerId))).size === 6
    )
  }

  const is_complete = is_squad_complete(squad)

  function handle_join_error(cause) {
    console.error('Error al unirse al amistoso:', {
      status: cause.status,
      error_code: cause.error_code,
      message: cause.message,
      room_id: room.room_id,
    })

    const code = cause.error_code
    const message = cause.message || 'Ocurrió un error inesperado.'

    // El código de error es más fiable que clasificar solo por el texto.
    if (code === 'UNAUTHORIZED' || cause.status === 401) {
      set_notice({
        kind: 'other',
        title: 'Sesión vencida',
        message: ERROR_MESSAGES.UNAUTHORIZED,
      })
      return
    }

    if (code === 'ROOM_NOT_FOUND' || cause.status === 404) {
      set_notice({
        kind: 'invalid_room',
        title: 'No se encontró la sala',
        message: ERROR_MESSAGES.ROOM_NOT_FOUND,
      })
      return
    }

    if (code === 'MATCH_ALREADY_STARTED') {
      set_notice({
        kind: 'full',
        title: 'Partido ya iniciado',
        message: ERROR_MESSAGES.MATCH_ALREADY_STARTED,
      })
      return
    }

    if (code === 'INVALID_SQUAD') {
      set_notice({
        kind: 'invalid_selection',
        title: 'Selección no válida',
        message: `${ERROR_MESSAGES.INVALID_SQUAD} Detalle: ${message}`,
      })
      return
    }

    // Compatibilidad con respuestas que aún no incluyen error_code.
    if (
      cause.status === 400 &&
      /jugador|comportamiento|selecci[oó]n|squad/i.test(message)
    ) {
      set_notice({
        kind: 'invalid_selection',
        title: 'Selección no válida',
        message: `${message} Revisá los seis puestos y sus comportamientos.`,
      })
      return
    }

    if (
      cause.status === 400 &&
      /completa|iniciad|started|full/i.test(message)
    ) {
      set_notice({
        kind: 'full',
        title: 'Sala no disponible',
        message,
      })
      return
    }

    if (cause.status === 422) {
      set_notice({
        kind: 'other',
        title: 'Datos no válidos',
        message: `El servidor rechazó los datos enviados: ${message}`,
      })
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

  async function confirm() {
  if (!is_complete || submitting) return

  set_submitting(true)

  const payload = {
    room_id: room.room_id,
    code: room.code,
    starters: squad.starters.map((slot) => ({
      player_id: String(slot.playerId),
      behavior_id: String(slot.behaviorId),
    })),
    substitutes: squad.substitutes.map((slot) => ({
      player_id: String(slot.playerId),
      behavior_id: String(slot.behaviorId),
    })),
  }

  try {
    console.debug('Enviando equipo para unirse al amistoso:', {
      room_id: payload.room_id,
      has_code: Boolean(payload.code),
      starters: payload.starters,
      substitutes: payload.substitutes,
    })

    // Si llegamos acá, el backend aceptó la incorporación.
    await join_friendly_room(payload)

    // IMPORTANTE:
    // No volver al menú. Entramos directamente a la sala.
    navigate(`/amistosos/${room.room_id}/sala`, {
      replace: true,
    })
  } catch (cause) {
    if (cause.name !== 'AbortError') {
      handle_join_error(cause)
    }
  } finally {
    set_submitting(false)
  }
  }

  function retry_selection() {
    set_notice(null)
    set_squad(EMPTY_SQUAD())
    set_load_status('loading')
    set_attempt((current) => current + 1)
  }

  function enter_other_code() {
    set_notice(null)
    set_change_open(true)
  }

  function change_room({ room_id, code }) {
    set_room({ room_id, code })
    set_change_open(false)
    set_notice(null)
  }

  function retry_load() {
    set_load_error('')
    set_load_status('loading')
    set_attempt((current) => current + 1)
  }

  return (
    <div className="home-page">
      <main className="home-content">
        <section className="home-welcome" aria-labelledby="join-title">
          <h1 id="join-title">Unirse a amistoso</h1>
          <p>Sala: {room.room_id}</p>

          <div className="join-row">
            <button
              className="home-action"
              onClick={() => navigate('/home')}
            >
              Volver
            </button>

            <button
              className="home-action"
              onClick={() => set_change_open(true)}
            >
              Cambiar sala
            </button>
          </div>
        </section>

        {load_status === 'loading' && (
          <div className="home-notice" role="status">
            Cargando tus jugadores y comportamientos…
          </div>
        )}

        {load_status === 'error' && (
          <>
            <p className="home-notice home-error" role="alert">
              {load_error}
            </p>

            <button className="home-action" onClick={retry_load}>
              Reintentar
            </button>
          </>
        )}

        {load_status === 'ready' && (
          <>
            {players.length < 6 && (
              <p className="home-notice" role="alert">
                Tenés {players.length} jugadores. Necesitás al menos 6
                jugadores distintos para completar titulares y suplentes.
              </p>
            )}

            {behaviors.length === 0 && (
              <p className="home-notice" role="alert">
                No hay comportamientos disponibles. No vas a poder confirmar
                hasta que el servidor devuelva al menos uno.
              </p>
            )}

            <section className="join-panel" aria-labelledby="join-team-title">
              <h2 id="join-team-title">Elegí tu equipo</h2>
              <p>
                Seleccioná 3 titulares y 3 suplentes. Cada puesto necesita un
                jugador y un comportamiento. Un jugador no puede ocupar dos
                puestos.
              </p>

              <SquadSelector
                players={players}
                behaviors={behaviors}
                squad={squad}
                setSquad={set_squad}
              />
            </section>

            <div className="join-row">
              <button
                className="home-action"
                onClick={confirm}
                disabled={!is_complete || submitting}
              >
                {submitting ? 'Uniéndote…' : 'Confirmar y unirse'}
              </button>

              {!is_complete && (
                <p className="join-hint" role="status">
                  Completá los seis puestos con jugadores distintos y asignales
                  un comportamiento.
                </p>
              )}
            </div>
          </>
        )}
      </main>

      <NoticeDialog notice={notice}>
        {notice?.kind === 'invalid_room' && (
          <button
            className="home-action"
            onClick={enter_other_code}
          >
            Ingresar otra sala
          </button>
        )}

        {notice?.kind === 'invalid_selection' && (
          <button
            className="home-action"
            onClick={retry_selection}
          >
            Volver a seleccionar
          </button>
        )}

        {notice?.kind === 'other' && (
          <button
            className="home-action"
            onClick={() => set_notice(null)}
          >
            Cerrar
          </button>
        )}

        {['success', 'full', 'invalid_room'].includes(notice?.kind) && (
          <button
            className="home-action"
            onClick={() => navigate('/home')}
          >
            Volver al menú
          </button>
        )}
      </NoticeDialog>

      <JoinFriendlyModal
        open={change_open}
        on_close={() => set_change_open(false)}
        on_submit={change_room}
      />
    </div>
  )
}