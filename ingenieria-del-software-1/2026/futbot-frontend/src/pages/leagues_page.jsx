import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { read_session } from '../auth/session'
import LeagueStandingsTable from '../components/LeagueStandingsTable'
import { useLeaguesSocket } from '../hooks/use_leagues_socket'
import './Home.css'
import './leagues_page.css'

function participants_label(count) {
  return `${count} ${count === 1 ? 'participante' : 'participantes'}`
}

function league_word(count) {
  return count === 1 ? 'liga' : 'ligas'
}

export default function LeaguesPage() {
  const navigate = useNavigate()
  const [search_text, set_search_text] = useState('')  // lo que escribe el usuario
  const [query, set_query] = useState('')              // el filtro que ya se aplicó
  const [selected, set_selected] = useState(null)      // liga elegida para unirse

  // Cada vez que llega un listado se refrescan los datos de la liga elegida
  const refresh_selected = useCallback((loaded, name) => {
    set_selected((current) => {
      if (!current) return current
      const updated = loaded.find((league) => league.id === current.id)
      if (updated) return updated
      return name ? current : null    // con filtro, que no aparezca no significa que haya desaparecido
    })
  }, [])

  const { data, connection } = useLeaguesSocket(query, refresh_selected)

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

  // Mientras no llegue el listado de la búsqueda actual, se muestra "Cargando"
  const loading = !data || data.name !== query
  const leagues = data?.leagues ?? []

  function search(event) {
    event.preventDefault()
    set_query(search_text.trim())
  }

  function clear_search() {
    set_search_text('')
    set_query('')
  }

  return (
    <div className="home-page">
      <main className="home-content" aria-busy={loading}>
        <section className="home-welcome" aria-labelledby="leagues-title">
          <h1 id="leagues-title">Ligas disponibles</h1>
          <p>Buscá una liga por nombre y seleccioná aquella en la que querés participar. El listado se actualiza solo.</p>
          <div className="leagues-row">
            <button className="home-action" onClick={() => navigate('/home')}>Volver</button>
          </div>
        </section>

        <form className="leagues-search" role="search" onSubmit={search}>
          <div>
            <label htmlFor="leagues-name">Buscar por nombre</label>
            <input
              id="leagues-name"
              type="search"
              value={search_text}
              onChange={(event) => set_search_text(event.target.value)}
              placeholder="Nombre de la liga"
              maxLength={80}
              autoComplete="off"
            />
          </div>
          <button type="submit" className="home-action">Buscar</button>
          {(search_text || query) && (
            <button type="button" className="home-action" onClick={clear_search}>Limpiar</button>
          )}
        </form>

        {selected && (
          <section className="leagues-selection" aria-labelledby="leagues-selected-title">
            <h2 id="leagues-selected-title">Liga seleccionada: {selected.name}</h2>
            <p>{participants_label(selected.participants_count)} · {selected.started ? 'Iniciada' : 'Sin iniciar'}</p>
            <button className="home-action" onClick={() => navigate(`/ligas/${encodeURIComponent(selected.id)}/unirse`)}>Unirse a Liga</button>
            <button className="home-action" onClick={() => set_selected(null)}>Quitar selección</button>
            <LeagueStandingsTable leagueId={selected.id} />
          </section>
        )}

        {connection === 'offline' && (
          <p className="home-notice home-error" role="alert">
            Sin conexión con el servidor. Reintentando…
          </p>
        )}

        {loading && <div className="home-notice" role="status">Cargando ligas…</div>}

        {!loading && leagues.length === 0 && (
          <p className="home-notice" role="status">
            {query
              ? `No hay ligas que coincidan con "${query}".`
              : 'Todavía no hay ligas disponibles.'}
          </p>
        )}

        {!loading && leagues.length > 0 && <>
          <p className="leagues-count" role="status">
            {leagues.length} {league_word(leagues.length)}{query ? ` para "${query}"` : ''}
          </p>
          <ul className="leagues-list">
            {leagues.map((league) => {
              const is_selected = selected?.id === league.id
              return (
                <li key={league.id} className={`leagues-item${is_selected ? ' leagues-item--selected' : ''}`}>
                  <h2>{league.name}</h2>
                  <p className="leagues-meta">
                    <span>{participants_label(league.participants_count)}</span>
                    <span className={`leagues-chip ${league.started ? 'leagues-chip--started' : 'leagues-chip--open'}`}>
                      {league.started ? 'Iniciada' : 'Sin iniciar'}
                    </span>
                  </p>
                  <button
                    className="home-action"
                    aria-pressed={is_selected}
                    onClick={() => set_selected(is_selected ? null : league)}
                  >
                    {is_selected ? 'Seleccionada' : 'Seleccionar'}
                  </button>
                </li>
              )
            })}
          </ul>
        </>}
      </main>
    </div>
  )
}