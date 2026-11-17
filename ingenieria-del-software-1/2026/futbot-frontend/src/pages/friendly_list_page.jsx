import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { read_session } from '../auth/session'
import Spinner from '../components/atoms/spinner'
import { usePublicFriendlySocket } from '../hooks/use_public_friendly_socket'
import './Home.css'
import './friendly_list_page.css'

const STATUS_LABELS = {
  waitingGuest: 'Esperando rival',
  readyToStart: 'Lista para iniciar',
  inProgress: 'En curso',
  finished: 'Finalizada',
}

const date_format = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium', timeStyle: 'short', hour12: false })

const normalize = (text) => text.trim().toLocaleLowerCase('es')

export default function FriendlyListPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const squad = location.state?.squad ?? null          // plantilla de un intento anterior (sala ocupada)
  const { rooms, connection } = usePublicFriendlySocket()
  const [search_text, set_search_text] = useState('')

  // Sin sesión no hay nada que mostrar; si vence o el canal rechaza el token, vuelve al login
  useEffect(() => {
    if (!read_session()) {
      navigate('/login', { replace: true })
      return
    }
    const unauthorized = () => navigate('/login', { replace: true })
    window.addEventListener('futbot:unauthorized', unauthorized)
    return () => window.removeEventListener('futbot:unauthorized', unauthorized)
  }, [navigate])

  const loading = rooms === null
  const query = search_text.trim()

  // El filtro se aplica sobre lo último que mandó el servidor: cada cambio en vivo lo respeta
  const visible = useMemo(() => {
    if (!rooms) return []
    const needle = normalize(search_text)
    if (!needle) return rooms
    return rooms.filter((room) => normalize(room.home_club_name).includes(needle))
  }, [rooms, search_text])

  // Si la sala ya no está disponible, lo informa el endpoint de unión (pantalla siguiente)
  function join(room) {
    navigate('/friendly/join', { state: { room_id: room.id, home_club_name: room.home_club_name, squad } })
  }

  return (
    <div className="home-page">
      <main className="home-content" aria-busy={loading}>
        <section className="home-welcome" aria-labelledby="friendly-title">
          <h1 id="friendly-title">Amistosos disponibles</h1>
          <p>Elegí una sala en espera de rival y unite con tu equipo. El listado se actualiza solo.</p>
          <div className="friendly-row">
            <button className="home-action" onClick={() => navigate('/home')}>Volver</button>
          </div>
        </section>

        {squad && (
          <p className="home-notice" role="note">
            Tu plantilla se conserva: elegí otra sala para unirte con ella.
          </p>
        )}

        {!loading && (
          <form className="friendly-search" role="search" onSubmit={(event) => event.preventDefault()}>
            <div>
              <label htmlFor="friendly-name">Buscar por nombre del club</label>
              <input
                id="friendly-name"
                type="search"
                value={search_text}
                onChange={(event) => set_search_text(event.target.value)}
                placeholder="Nombre del club local"
                maxLength={80}
                autoComplete="off"
              />
            </div>
            {search_text && (
              <button type="button" className="home-action" onClick={() => set_search_text('')}>Limpiar</button>
            )}
          </form>
        )}

        {connection === 'offline' && (
          <p className="home-notice home-error" role="alert">
            Sin conexión con el servidor. Reintentando…
          </p>
        )}

        {loading && (
          <div className="home-notice friendly-loading" role="status">
            <Spinner />
            Cargando amistosos…
          </div>
        )}

        {!loading && visible.length === 0 && (
          <p className="home-notice" role="status">
            {rooms.length === 0
              ? 'No hay amistosos disponibles.'
              : `No hay amistosos que coincidan con "${query}".`}
          </p>
        )}

        {!loading && query && visible.length > 0 && (
          <p className="friendly-count" role="status">
            {visible.length} de {rooms.length} {rooms.length === 1 ? 'sala' : 'salas'}
          </p>
        )}

        {!loading && visible.length > 0 && (
          <ul className="friendly-list">
            {visible.map((room) => {
              const club = room.home_club_name || 'Club sin nombre'
              return (
                <li key={room.id} className="friendly-item">
                  <h2>{club}</h2>
                  <p className="friendly-meta">
                    <span className="friendly-chip">{STATUS_LABELS[room.status] ?? room.status}</span>
                    <span>
                      Creada{' '}
                      {room.created_at
                        ? <time dateTime={room.created_at.toISOString()}>{date_format.format(room.created_at)}</time>
                        : '—'}
                    </span>
                  </p>
                  <button
                    className="home-action"
                    aria-label={`Unirse a la sala de ${club}`}
                    onClick={() => join(room)}
                  >
                    Unirse
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </main>
    </div>
  )
}