import './atoms.css'

// variant: 'default' | 'ok' | 'warning'
function Chip({ variant = 'default', children }) {
  return <span className={`fb-chip fb-chip--${variant}`}>{children}</span>
}

export default Chip
