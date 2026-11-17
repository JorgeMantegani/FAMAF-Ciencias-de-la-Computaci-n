import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { get_club_ranking } from '../api/clubs'
import { read_session } from '../auth/session'
import ClubAvatar from '../components/ClubAvatar'
import PublicProfileModal from '../components/PublicProfileModal'
import './Home.css'
import './ranking_page.css'

const PAGE_SIZE = 20
const MEDALS = ['🥇', '🥈', '🥉']

export default function RankingPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState(null)
  const [selectedClub, setSelectedClub] = useState(null)
  const requestKey = `${page}:${attempt}`
  const session = read_session()
  const clubId = session?.club_id

  useEffect(() => {
    if (!read_session()) {
      navigate('/login', { replace: true })
      return
    }
    const unauthorized = () => navigate('/login', { replace: true })
    window.addEventListener('futbot:unauthorized', unauthorized)
    return () => window.removeEventListener('futbot:unauthorized', unauthorized)
  }, [navigate])

  useEffect(() => {
    if (!clubId) return
    const controller = new AbortController()
    get_club_ranking({ page, size: PAGE_SIZE, signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ requestKey, data, status: 'ready' })
      })
      .catch((error) => {
        if (controller.signal.aborted || error.name === 'AbortError') return
        if (error.status === 401) { navigate('/login', { replace: true }); return }
        setResult({ requestKey, status: 'error' })
      })
    return () => controller.abort()
  }, [clubId, page, requestKey, navigate])

  const current = result?.requestKey === requestKey ? result : { status: 'loading' }
  const data = current.data
  const loading = current.status === 'loading'

  return (
    <div className="home-page">
      <div className="home-content ranking-page" aria-busy={loading}>
        <header className="home-welcome">
          <h1>Ranking de clubes</h1>
          <p>Conocé la clasificación global y explorá los clubes rivales.</p>
          <Link className="home-action" to="/home">Volver al inicio</Link>
        </header>
        {loading && <section className="ranking-panel" role="status" aria-label="Cargando ranking">
          <span>Cargando ranking…</span>
          {Array.from({ length: 5 }, (_, index) => <div key={index} className="ranking-skeleton" aria-hidden="true" />)}
        </section>}
        {current.status === 'error' && <section className="ranking-panel">
          <p role="alert">No se pudo cargar el ranking. Intentá nuevamente.</p>
          <button className="home-action" onClick={() => setAttempt((value) => value + 1)}>Reintentar</button>
        </section>}
        {data && <section className="ranking-panel" aria-label="Clasificación global">
          <p className="ranking-summary">Tu posición: <strong>#{data.userClubRanking.position}</strong> · {data.userClubRanking.rankingPoints} puntos</p>
          <p>{data.totalClubs} clubes en la clasificación</p>
          {data.items.length === 0 ? <p role="status">No hay clubes en esta página.</p> : (
            <div className="ranking-scroll">
              <table className="ranking-table">
                <caption className="ranking-sr-only">Ranking de clubes, página {data.page}</caption>
                <thead><tr><th scope="col">Posición</th><th scope="col">Club</th><th scope="col">Puntos</th></tr></thead>
                <tbody>{data.items.map((club) => {
                  const own = club.clubId === clubId
                  return <tr key={club.clubId} className={`${own ? 'ranking-own-club' : ''} ${club.position <= 3 ? `ranking-top-${club.position}` : ''}`}>
                    <td><span className="ranking-position">{club.position <= 3 && <span role="img" aria-label={`Medalla del puesto ${club.position}`}>{MEDALS[club.position - 1]}</span>} {club.position}</span></td>
                    <th scope="row"><button className="ranking-club-button" aria-label={`Ver perfil de ${club.clubName}`} onClick={() => setSelectedClub(club)}>
                      <ClubAvatar avatar={club.avatar} clubName={club.clubName} />
                      <span>{club.clubName}{own && <span className="ranking-own-label">Tu club</span>}</span>
                    </button></th>
                    <td>{club.rankingPoints}</td>
                  </tr>
                })}</tbody>
              </table>
            </div>
          )}
          <nav className="ranking-pagination" aria-label="Paginación del ranking">
            <button className="home-action" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Anterior</button>
            <span aria-live="polite">Página {data.page} de {data.totalPages}</span>
            <button className="home-action" disabled={page >= data.totalPages} onClick={() => setPage((value) => value + 1)}>Siguiente</button>
          </nav>
        </section>}
      </div>
      {selectedClub && <PublicProfileModal clubId={selectedClub.clubId} club={selectedClub} onClose={() => setSelectedClub(null)} />}
    </div>
  )
}
