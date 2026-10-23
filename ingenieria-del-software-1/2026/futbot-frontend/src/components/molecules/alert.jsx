import Icon from '../atoms/icon'
import './molecules.css'

// variant: 'error' | 'info'
function Alert({ variant = 'error', children }) {
  return (
    <div
      className={`fb-alert fb-alert--${variant}`}
      role={variant === 'error' ? 'alert' : 'status'}
    >
      <Icon name={variant === 'error' ? 'alert' : 'info'} />
      <span>{children}</span>
    </div>
  )
}

export default Alert
