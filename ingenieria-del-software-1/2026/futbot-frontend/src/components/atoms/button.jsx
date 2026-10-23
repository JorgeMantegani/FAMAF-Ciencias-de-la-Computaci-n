import Spinner from './spinner'
import './atoms.css'

// variant: 'primary' | 'ghost'
function Button({
  variant = 'primary',
  isLoading = false,
  disabled = false,
  children,
  ...props
}) {
  return (
    <button
      type="button"
      className={`fb-button fb-button--${variant}`}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {isLoading && <Spinner />}
      <span className="fb-button__content">{children}</span>
    </button>
  )
}

export default Button
