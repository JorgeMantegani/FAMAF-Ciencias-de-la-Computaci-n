import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../api/auth'
import EmailVerificationLayout from '../components/email_verification_layout'
import './password_reset.css'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const pending = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (pending.current || !event.currentTarget.reportValidity()) return
    pending.current = true
    setStatus('loading')
    setError('')
    try {
      await forgotPassword(email.trim())
      setEmail('')
      setStatus('success')
    } catch (cause) {
      setError(cause.status
        ? 'No se pudo solicitar el enlace. Intentá nuevamente.'
        : 'No se pudo conectar con el servidor. Intentá nuevamente.')
      setStatus('idle')
    } finally {
      pending.current = false
    }
  }

  return (
    <EmailVerificationLayout>
      <h1>Recuperar contraseña</h1>
      {status === 'success' ? (
        <p role="status">Si el correo está registrado, recibirás un enlace para restablecer tu contraseña en los próximos minutos.</p>
      ) : (
        <>
          <p>Ingresá el email de tu cuenta para solicitar un enlace de recuperación.</p>
          <form className="password-reset-form" onSubmit={submit} aria-busy={status === 'loading'}>
            <label htmlFor="recovery-email">Email</label>
            <input id="recovery-email" name="email" type="email" autoComplete="email" required
              value={email} onChange={(event) => setEmail(event.target.value)} disabled={status === 'loading'} />
            {error && <p role="alert">{error}</p>}
            <button type="submit" disabled={status === 'loading'}>
              {status === 'loading' ? 'Solicitando enlace…' : 'Enviar enlace de recuperación'}
            </button>
          </form>
        </>
      )}
      <Link to="/login">Volver a Iniciar Sesión</Link>
    </EmailVerificationLayout>
  )
}
