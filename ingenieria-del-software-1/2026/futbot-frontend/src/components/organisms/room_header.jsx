import Chip from '../atoms/chip'
import Panel from '../atoms/panel'
import './organisms.css'

// status: { label, variant } already resolved by the page.
function RoomHeader({ title, status, description, roomCode, actions }) {
  return (
    <Panel className="fb-room-header">
      <div className="fb-room-header__text">
        <div className="fb-room-header__title-row">
          <h1 className="fb-heading fb-room-header__title">{title}</h1>
          <Chip variant={status.variant}>{status.label}</Chip>
        </div>
        <p className="fb-room-header__description">{description}</p>
        {roomCode && (
          <p className="fb-label">
            Código de sala: <span className="fb-room-header__code">{roomCode}</span>
          </p>
        )}
      </div>
      <div className="fb-room-header__actions">{actions}</div>
    </Panel>
  )
}

export default RoomHeader
