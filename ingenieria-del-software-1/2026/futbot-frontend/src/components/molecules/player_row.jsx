import Chip from '../atoms/chip'
import Icon from '../atoms/icon'
import './molecules.css'

const ROLE_LABELS = { starter: 'Titular', substitute: 'Suplente' }

// side: 'home' | 'away', only changes the number badge color.
function PlayerRow({ number, player, side }) {
  return (
    <li className="fb-player-row">
      <span className={`fb-player-row__number fb-player-row__number--${side}`}>
        {number}
      </span>
      <span className="fb-player-row__info">
        <span className="fb-player-row__name">{player.name}</span>
        <span className="fb-player-row__role">{ROLE_LABELS[player.role]}</span>
      </span>
      <span className="fb-player-row__behavior">
        <Chip>
          <Icon name="code" size={12} />
          <span translate="no">{player.behaviorName}</span>
        </Chip>
      </span>
    </li>
  )
}

export default PlayerRow
