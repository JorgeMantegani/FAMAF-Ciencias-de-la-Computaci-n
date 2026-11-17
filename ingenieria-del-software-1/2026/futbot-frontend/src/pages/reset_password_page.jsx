import { useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { resetPassword } from '../api/auth'
import { clear_session } from '../auth/session'
import EmailVerificationLayout from '../components/email_verification_layout'
import './password_reset.css'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  return <ResetPasswordForm key={token} token={token} />
}

function ResetPasswordForm({ token }) {
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [storageWarning, setStorageWarning] = useState('')
  const pending = useRef(false)
  const length = Array.from(password).length
  const validLength = length >= 8 && length <= 20
  const mismatch = confirmation.length > 0 && password !== confirmation
  const valid = validLength && password === confirmation
  const missingToken = !token.trim()

  async function submit(event) {
    event.preventDefault()
    if (pending.current || missingToken || !valid || !event.currentTarget.reportValidity()) return
    pending.current = true
    setStatus('loading')
    setError('')
    try {
      await resetPassword(token, password)
    } catch (cause) {
      if (['PASSWORD_RESET_TOKEN_INVALID', 'PASSWORD_RESET_TOKEN_EXPIRED'].includes(cause.error_code)) {
        setStatus('invalid')
        setPassword('')
        setConfirmation('')
      } else {
        setError(cause.status
          ? 'No se pudo actualizar la contraseña. Intentá nuevamente.'
          : 'No se pudo conectar con el servidor. Intentá nuevamente.')
        setStatus('idle')
      }
      pending.current = false
      return
    }
    // El cambio en el servidor ya se completó, aunque el navegador bloquee el almacenamiento.
    try {
      clear_session()
    } catch {
      setStorageWarning('No se pudo limpiar la sesión del navegador. Cerrá la sesión anterior antes de volver a ingresar.')
    }
    setPassword('')
    setConfirmation('')
    setStatus('success')
    pending.current = false
  }

  return (
    <EmailVerificationLayout>
      <h1>Restablecer contraseña</h1>
      {missingToken || status === 'invalid' ? (
        <>
          <p role="alert">{missingToken
            ? 'El enlace no contiene un token de recuperación.'
            : 'El enlace de recuperación ha caducado o es inválido'}</p>
          <Link className="email-action" to="/forgot-password">Solicitar nuevo enlace</Link>
        </>
      ) : status === 'success' ? (
        <>
          <p role="status">Contraseña actualizada correctamente</p>
          {storageWarning && <p role="alert">{storageWarning}</p>}
          <Link className="email-action" to="/login">Ir a Iniciar Sesión</Link>
        </>
      ) : (
        <form className="password-reset-form" onSubmit={submit} aria-busy={status === 'loading'}>
          <p id="password-requirements">La nueva contraseña debe tener entre 8 y 20 caracteres.</p>
          <label htmlFor="new-password">Nueva contraseña</label>
          <input id="new-password" name="newPassword" type="password" autoComplete="new-password" required
            aria-describedby="password-requirements" aria-invalid={password.length > 0 && !validLength}
            value={password} onChange={(event) => setPassword(event.target.value)} disabled={status === 'loading'} />
          {password.length > 0 && !validLength && <p role="alert">La contraseña debe tener entre 8 y 20 caracteres.</p>}
          <label htmlFor="confirm-password">Confirmar nueva contraseña</label>
          <input id="confirm-password" name="confirmPassword" type="password" autoComplete="new-password" required
            aria-invalid={mismatch} aria-describedby={mismatch ? 'password-mismatch' : undefined}
            value={confirmation} onChange={(event) => setConfirmation(event.target.value)} disabled={status === 'loading'} />
          {mismatch && <p id="password-mismatch" role="alert">Las contraseñas no coinciden.</p>}
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={!valid || status === 'loading'}>
            {status === 'loading' ? 'Actualizando contraseña…' : 'Actualizar contraseña'}
          </button>
          <Link to="/forgot-password">Solicitar nuevo enlace</Link>
        </form>
      )}
    </EmailVerificationLayout>
  )
}
