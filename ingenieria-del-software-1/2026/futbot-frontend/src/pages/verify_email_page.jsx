import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { verifyEmail } from '../api/auth'
import EmailVerificationLayout from '../components/email_verification_layout'
import ResendVerificationForm from '../components/resend_verification_form'

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  return <Verification key={token} token={token} />
}

function Verification({ token }) {
  const [result, setResult] = useState(null)
  // Share the pending request between StrictMode effect setups, without persisting the token.
  const pending = useRef(null)

  useEffect(() => {
    if (!token) return
    let active = true
    if (!pending.current) pending.current = verifyEmail(token)
    pending.current.then(
      () => { if (active) setResult({ success: true }) },
      (cause) => {
        if (active) setResult({ error: cause.status ? cause.message : 'No se pudo conectar con el servidor. Volvé a abrir el enlace o solicitá uno nuevo.' })
      },
    )
    return () => { active = false }
  }, [token])

  const error = !token ? 'El enlace no contiene un token de verificación.' : result?.error
  return (
    <EmailVerificationLayout>
      <h1>Validación de cuenta</h1>
      {!error && !result && <p role="status" aria-live="polite">Validando tu correo…</p>}
      {result?.success && <>
        <p role="status">Tu correo fue verificado correctamente. Ya podés iniciar sesión.</p>
        <Link className="email-action" to="/login">Ir a Iniciar Sesión</Link>
      </>}
      {error && <>
        <p role="alert">{error}</p>
        <ResendVerificationForm />
      </>}
    </EmailVerificationLayout>
  )
}
