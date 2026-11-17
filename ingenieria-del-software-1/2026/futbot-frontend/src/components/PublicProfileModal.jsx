import { useEffect, useRef } from 'react'
import Modal from './modal'
import ClubAvatar from './ClubAvatar'

// Datos públicos ya recibidos del ranking; no requiere otra petición HTTP.
export default function PublicProfileModal({ clubId, club, onClose }) {
  const closeButton = useRef(null)
  useEffect(() => {
    const previousFocus = document.activeElement
    closeButton.current?.focus()
    return () => previousFocus?.focus()
  }, [])

  if (!club || club.clubId !== clubId) return null
  return (
    <Modal title={`Perfil público de ${club.clubName}`} onClose={onClose}>
      <div className="ranking-profile">
        <ClubAvatar avatar={club.avatar} clubName={club.clubName} />
        <h3>{club.clubName}</h3>
        <dl>
          <dt>Posición global</dt><dd>{club.position}</dd>
          <dt>Puntos</dt><dd>{club.rankingPoints}</dd>
        </dl>
        <button ref={closeButton} className="home-action" onClick={onClose}
          onKeyDown={(event) => {
            if (event.key === 'Tab') { event.preventDefault(); closeButton.current?.focus() }
          }}>Cerrar perfil</button>
      </div>
    </Modal>
  )
}
