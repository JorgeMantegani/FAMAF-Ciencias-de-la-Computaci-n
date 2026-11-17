import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { get_current_user, logout as logout_session } from '../api/client'
import { clear_session, read_session, save_session } from '../auth/session'
import CreateFriendlyModal from '../components/CreateFriendlyModal'
import Modal from '../components/modal';
import CreatePlayerForm from '../components/create_player_form';
import CreateLeagueForm from '../components/create_league_form';
import ActiveRoomsModal from '../components/ActiveRoomsModal';

import './Home.css'

import JoinPrivateLeagueModal from '../components/join_private_league_modal'

export default function Home() {
  const navigate = useNavigate()
  const [status, set_status] = useState('loading')
  const [error, set_error] = useState('')
  const [attempt, set_attempt] = useState(0)
  const [closing, set_closing] = useState(false)
  const [create_open, set_create_open] = useState(false)
  const [private_league_open, set_private_league_open] = useState(false)
  const [show_form, setShow_form] = useState(false);
  const [show_success, setShow_success] = useState(false);
  const [show_league_form, setShow_league_form] = useState(false);
  const [active_rooms_open, set_active_rooms_open] = useState(false);

  // Al crear el jugador se cierra el formulario y se muestra el pop-up de éxito
  const handle_success = () => {
    setShow_form(false);
    setShow_success(true);
  };

  useEffect(() => {
    const session = read_session()
    if (!session) {
      navigate('/login', { replace: true })
      return
    }
    const controller = new AbortController()
    const unauthorized = () => navigate('/login', { replace: true })
    let expiry_timer
    const check_expiration = () => {
      clearTimeout(expiry_timer)
      const current = read_session()
      if (!current) {
        unauthorized()
        return
      }
      expiry_timer = setTimeout(check_expiration, Math.min(current.expires_at * 1000 - Date.now(), 2147483647))
    }
    const storage_changed = (event) => {
      if (event.key === 'futbot.session' || event.key === null) check_expiration()
    }
    check_expiration()
    window.addEventListener('focus', check_expiration)
    document.addEventListener('visibilitychange', check_expiration)
    window.addEventListener('storage', storage_changed)
    window.addEventListener('futbot:unauthorized', unauthorized)
    get_current_user({ signal: controller.signal }).then((user) => {
      if (controller.signal.aborted) return
      // El club autorizado lo determina el servidor.
      const current = read_session()
      if (!current) return
      save_session({ ...current, club_id: user.club_id })
      set_status('ready')
    }).catch((cause) => {
      if (controller.signal.aborted || cause.name === 'AbortError') return
      if (cause.status === 401) {
        clear_session()
        unauthorized()
        return
      }
      set_error(cause.status ? cause.message : 'No se pudo verificar la sesión. Intentá nuevamente.')
      set_status('error')
    })
    return () => {
      controller.abort()
      clearTimeout(expiry_timer)
      window.removeEventListener('focus', check_expiration)
      document.removeEventListener('visibilitychange', check_expiration)
      window.removeEventListener('futbot:unauthorized', unauthorized)
      window.removeEventListener('storage', storage_changed)
    }
  }, [navigate, attempt])

  async function logout() {
    if (closing) return
    set_closing(true)
    set_error('')
    try {
      await logout_session()
      navigate('/login', { replace: true })
    } catch {
      set_error('No se pudo cerrar la sesión en el servidor. Intentá nuevamente.')
    } finally {
      set_closing(false)
    }
  }

  function join_private_league(league) {
    set_private_league_open(false)
    const league_id = encodeURIComponent(league.leagueId)
    navigate(league.isEnrolled ? `/league/${league_id}/waiting` : `/ligas/${league_id}/unirse`)
  }

  return (
    <div className="home-page">
      <header className="home-topbar">
        <div className="home-identity">
          <span className="home-mark"><HomeIcon /></span>
          <div>
            <p className="home-product">FutBot</p>
            <p className="home-project">laboratorio / presión alta v4</p>
          </div>
        </div>
        <div className="home-session">
          <Link className="home-action" to="/ranking">Ranking de clubes</Link>
          {status === 'ready' && <span className="home-session-state"><span aria-hidden="true" /> Club en línea</span>}
          <button className="home-action" onClick={logout} disabled={closing}>
            {closing ? 'Cerrando sesión…' : 'Cerrar sesión'}
          </button>
        </div>
      </header>

      <main className="home-content" aria-busy={status === 'loading'}>
        {status === 'loading' && <div className="home-notice" role="status">Verificando sesión…</div>}
        {error && <p className="home-notice home-error" role="alert">{error}</p>}
        {status === 'error' && (
          <button className="home-action" onClick={() => { set_error(''); set_status('loading'); set_attempt(attempt + 1) }}>
            Reintentar
          </button>
        )}
        {status === 'ready' && (
          <>
            <section className="home-welcome" aria-labelledby="home-title">
              <h1 id="home-title">Menú principal</h1>
              <p>Bienvenido a tu club. Prepará tu equipo, diseñá tu estrategia y elegí tu próximo desafío.</p>
            </section>

            {/* Grilla para las tarjetas */}
            <div className="home-grid">

              <article className="home-card" aria-labelledby="home-card-match">
                <div className="home-card-content">
                  <h2 id="home-card-match">Estado del partido</h2>
                  <p>Ingresá el ID del partido para consultar su estado actual.</p>
                </div>
                <form className="match-entry" onSubmit={(event) => {
                  event.preventDefault()
                  const id = new FormData(event.currentTarget).get('match_id').trim()
                  if (id) navigate(`/partidos/${encodeURIComponent(id)}`)
                }}>
                  <label htmlFor="match_id">ID del partido</label>
                  <input id="match_id" name="match_id" required placeholder="Ingresá el ID del partido" />
                  <button className="home-action" type="submit">Ver partido</button>
                </form>
              </article>

              {/* Tarjeta de Club */}
              <article className="home-card" aria-labelledby="home-card-club">
                <div className="home-card-content">

                  {/* Icono de club */}
                  <div className="home-card-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                      <polyline points="9 22 9 12 15 12 15 22" />
                    </svg>
                  </div>

                  {/* Informacion de la tarjeta */}
                  <div>
                    <h2 id="home-card-club">Club</h2>
                    <p>Perfil personal con informacion de usuario y gestión de tus salas activas.</p>
                  </div>
                </div>

                {/* Boton de acceso */}
                <div className="home-card-actions">
                  <button className="home-action" onClick={() => set_active_rooms_open(true)}>
                    VER SALAS ACTIVAS
                  </button>
                </div>
              </article>


              {/* Tarjeta de Comportamientos */}
              <article className="home-card" aria-labelledby="home-card-behaviors" aria-describedby="home-card-behaviors-desc">
                <div className="home-card-content">

                  {/* Ícono de código */}
                  <div className="home-card-icon">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>

                  {/* Información de la tarjeta */}
                  <div>
                    <h2 id="home-card-behaviors">Comportamientos</h2>
                    <p id="home-card-behaviors-desc">
                      Define reglas, bloques y comportamientos para cada jugador antes de enviarlos al campo.
                    </p>
                  </div>
                </div>

                {/* Botón de acceso a la ruta */}
                <Link
                  to="/behaviors"
                  className="home-action"
                >
                  VER COMPORTAMIENTOS
                </Link>

                {/* Botón de acceso a la ruta */}
                <Link
                  to="/behaviors/create"
                  className="home-action"
                >
                  CREAR
                </Link>
              </article>

              {/* Tarjeta de Privados */}

              <article className="home-card" aria-labelledby="home-card-privates" aria-describedby="home-card-privates-desc">
                <div className="home-card-content">

                  {/* Icono de Privados */}
                  <div className="home-card-icon">
                    <svg viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0110 0v4" />
                    </svg>
                  </div>

                  {/* Informacion de la tarjeta */}
                  <div>
                    <h2>Unirse a liga privada / Amistoso</h2>
                    <p>
                      Únete a una liga privada o crea un partido amistoso con invitaciones personalizadas
                    </p>
                  </div>
                </div>
                {/* Botones de acción: crear y unirse */}
                <div className="home-card-actions">
                  <button className="home-action" onClick={() => set_create_open(true)}>
                    CREAR
                  </button>
                  <Link to="/friendly" className="home-action">
                    Unirse a un amistoso
                  </Link>
                  <button className="home-action" onClick={() => set_private_league_open(true)}>
                    Unirse a liga privada
                  </button>
                </div>
              </article>

              {/* Tarjeta crear jugador */}
              <article className="home-card" aria-labelledby="home-card-player">
                <div className="home-card-content">
                  <div className="home-card-icon">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <circle cx="12" cy="8" r="4" />
                      <path d="M4 21c0-4 3.5-7 8-7s8 3 8 7" />
                    </svg>
                  </div>

                  <div>
                    <h2 id="home-card-player">Crear jugador</h2>
                    <p>
                      Creá jugadores para tu club y repartí sus atributos.
                    </p>
                  </div>
                </div>

                <button
                  className="home-action"
                  type="button"
                  onClick={() => setShow_form(true)}
                >
                  CREAR JUGADOR
                </button>
              </article>

              {/* Tarjeta de Ligas */}
              <article className="home-card" aria-labelledby="home-card-leagues" aria-describedby="home-card-leagues-desc">
                <div className="home-card-content">
                  <div className="home-card-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
                      <circle cx="9" cy="7" r="4" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
                    </svg>
                  </div>
                  <div>
                    <h2 id="home-card-leagues">Ligas públicas</h2>
                    <p id="home-card-leagues-desc">
                      Explora torneos abiertos, clasificaciones y competencias disponibles para unirte
                    </p>
                  </div>
                </div>
                <Link to="/leagues" className="home-action">
                  VER LIGAS
                </Link>
              </article>

            </div>
            {show_form && (
              <Modal
                title="Crear Jugador"
                description="Elegí un nombre y repartí exactamente 300 puntos entre los cinco atributos (20 a 100 cada uno)."
                onClose={() => setShow_form(false)}
              >
                <CreatePlayerForm
                  onSuccess={handle_success}
                  onCancel={() => setShow_form(false)}
                />
              </Modal>
            )}

            {show_success && (
              <Modal
                title="Listo"
                onClose={() => setShow_success(false)}
              >
                <p className="mb-4">Jugador creado con éxito</p>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => setShow_success(false)}
                    className="h-10 rounded-[5px] bg-[#C9973B] px-3 text-xs font-semibold uppercase tracking-wide text-[#1A1A1A] hover:bg-[#D9A94D]"
                  >
                    Aceptar
                  </button>
                </div>
              </Modal>
            )}
            {/* Tarjeta crear liga */}
            <article className="home-card" aria-labelledby="home-card-league">
              <div className="home-card-content">
                <div>
                  <h2 id="home-card-league">Crear liga</h2>
                  <p>Configurá una liga, elegí tu plantel y compartí el código.</p>
                </div>
              </div>
              <button
                className="home-action"
                type="button"
                onClick={() => setShow_league_form(true)}
              >
                CREAR LIGA
              </button>
            </article>
            {show_league_form && (
              <Modal
                title="Crear Liga"
                description="Configurá la liga y elegí 3 titulares y 3 suplentes con su comportamiento."
                onClose={() => setShow_league_form(false)}
              >
                <CreateLeagueForm onCancel={() => setShow_league_form(false)} />
              </Modal>
            )}

          </>
        )}
      </main>
      <ActiveRoomsModal
        open={active_rooms_open}
        onClose={() => set_active_rooms_open(false)}
      />

      {private_league_open && (
        <JoinPrivateLeagueModal
          on_close={() => set_private_league_open(false)}
          on_found={join_private_league}
        />
      )}

      <CreateFriendlyModal
        isOpen={create_open}
        onClose={() => set_create_open(false)}
      />
    </div>
  )
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 8l8 8M16 8l-8 8" />
    </svg>
  )
}