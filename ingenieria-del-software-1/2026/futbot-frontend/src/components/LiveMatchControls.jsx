import './SubstitutionModal.css'

export default function LiveMatchControls({ status, visible = true, disabled, onOpen }) {
  if (!visible || !['in_progress', 'paused'].includes(String(status).toLowerCase())) return null

  return (
    <div className="live-match-controls">
      <button
        className="live-match-controls__button"
        type="button"
        disabled={disabled}
        onClick={onOpen}
      >
        <span aria-hidden="true">↻</span>
        Sustituir
      </button>
    </div>
  )
}
