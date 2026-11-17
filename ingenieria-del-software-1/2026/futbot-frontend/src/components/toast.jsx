import { useEffect } from 'react'

export default function Toast({ message, type = 'success', on_close, duration = 4000 }) {
  useEffect(() => {
    const timer = setTimeout(on_close, duration)
    return () => clearTimeout(timer)
  }, [message, duration, on_close])

  return (
    <div role={type === 'error' ? 'alert' : 'status'} className={`toast toast--${type}`}>
      <span>{message}</span>
      <button type="button" aria-label="Cerrar aviso" onClick={on_close}>×</button>
    </div>
  )
}