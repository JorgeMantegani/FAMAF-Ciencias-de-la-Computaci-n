import { useId, useRef, useState } from 'react'
import { resendVerification } from '../api/auth'
import '../pages/email_verification.css'

export default function ResendVerificationForm({ initialEmail = '' }) {
  const id = useId()
  const [email, setEmail] = useState(initialEmail)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const pending = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (pending.current || !event.currentTarget.reportValidity()) return
    pending.current = true
    setBusy(true)
    setMessage('')
    setError('')
    try {
      const result = await resendVerification(email.trim())
      setMessage(result?.detail || 'Si corresponde, recibirás un correo de verificación.')
    } catch (cause) {
      setError(cause.status ? cause.message : 'No se pudo conectar con el servidor. Intentá nuevamente.')
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return (
    <form className="email-resend" onSubmit={submit} aria-busy={busy}>
      <label htmlFor={id}>Email para recibir el enlace</label>
      <input id={id} type="email" autoComplete="email" required value={email}
        onChange={(event) => setEmail(event.target.value)} disabled={busy} />
      <button type="submit" disabled={busy}>{busy ? 'Solicitando enlace…' : 'Solicitar nuevo enlace'}</button>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
