import { useNavigate } from 'react-router-dom'
import { useState , useEffect } from "react"
import { createFriendlyRoom , getMyPlayers , getMyBehaviors } from "../api/friendly"
import SquadSelector from './SquadSelector'
import './CreateFriendlyModal.css'
import MiniPitchViewer from './mini_pitch_viewer'

export default function CreateFriendlyModal({ isOpen, onClose }) {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [players, setPlayers] = useState([])
    const [behaviors, setBehaviors] = useState([])

    const [squad, setSquad] = useState({
        starters: Array(3).fill({ playerId: '', behaviorId: '' }),
        substitutes: Array(3).fill({ playerId: '', behaviorId: '' }),
    })

    const [createdRoom, setCreatedRoom] = useState(null)

    const [preview_selection, set_preview_selection] = useState(null)

    function handle_preview(slot) {
      set_preview_selection({
        player_id: slot.playerId,
        behavior_id: slot.behaviorId,
      })
    }

    useEffect(() => {
        if (!isOpen) return
        let active = true
        Promise.all([getMyPlayers(), getMyBehaviors()])
            .then(([playersData, behaviorsData]) => {
                if (!active) return
                setPlayers(playersData)
                setBehaviors(behaviorsData)
            })
            .catch(() => {
                if (active) setError('Error al cargar la pantalla de jugadores y estrategias.')
            })
        return () => { active = false }
    }, [isOpen])

    const isSquadComplete = () => {
        const isSlotValid = (slot) => slot.playerId !== '' && slot.behaviorId !== ''
        return squad.starters.every(isSlotValid) && squad.substitutes.every(isSlotValid)
    }

    const handleCreateFriendly = async () => {
        setError(null)
        setLoading(true)
        
        const payload = {
            starters: squad.starters.map((s) => ({
                player_id: String(s.playerId),
                behavior_id: String(s.behaviorId),
            })),
            substitutes: squad.substitutes.map((s) => ({
                player_id: String(s.playerId),
                behavior_id: String(s.behaviorId),
            })),
        }

        try {
            const roomData = await createFriendlyRoom(payload)
            const roomID = roomData?.roomId || roomData?.room_id
            if (!roomID) {
                setError('El servidor no devolvió el ID de la sala.')
                return
            }
            navigate(`/amistosos/${roomID}/sala`)
        } catch (err) {
            let errorMsg = 'No fue posible crear amistoso.'
            const detailObj = err.detail || err.message
            if (Array.isArray(detailObj)) {
                errorMsg = detailObj
                    .map((e) => `Campo '${e.loc ? e.loc.join('.') : 'campo'}': ${e.msg}`)
                    .join(' | ')
            }else if (typeof detailObj === 'string') {
                errorMsg = detailObj
            }
            setError(errorMsg)
        } finally {
            setLoading(false)
        }
    }

    if (!isOpen) return null

    return (
    <div className="modal-overlay" onClick={onClose}>
      {preview_selection && (
        <MiniPitchViewer
          player_id={preview_selection.player_id}
          behavior_id={preview_selection.behavior_id}
          onClose={() => set_preview_selection(null)}
        />
      )}
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h1 className="text">Crear Partido Amistoso</h1>
        </div>

        {error && <div className="modal-alert modal-alert-danger">{error}</div>}

        {createdRoom ? (
          <div className="modal-success-box">
            <h3>¡Amistoso creado!</h3>
            <p>
              Tu sala ya aparece en el listado público de amistosos. Cuando otro club se una,
              podrás iniciar el partido.
            </p>
            <button className="home-action" onClick={() => {
              const roomID = createdRoom.roomId || createdRoom.room_id
              navigate(`/amistosos/${roomID}/sala`)}}>INICIAR</button>
            <button className="home-action" onClick={onClose}>Cerrar</button>
          </div>
        ) : (
          <div className="modal-body">
            <SquadSelector
              players={players}
              behaviors={behaviors}
              squad={squad}
              setSquad={setSquad}
              onPreview={handle_preview}
            />
            <div className="modal-actions">
              <button
                className="home-action"
                disabled={!isSquadComplete() || loading}
                onClick={handleCreateFriendly}
              >
                {loading ? 'Creando...' : 'Confirmar y Crear Sala'}
              </button>
              <button className="home-action secondary" disabled={loading} onClick={onClose}>
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
