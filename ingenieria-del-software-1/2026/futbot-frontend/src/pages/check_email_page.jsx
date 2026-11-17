import { Link, useLocation } from 'react-router-dom'
import EmailVerificationLayout from '../components/email_verification_layout'
import ResendVerificationForm from '../components/resend_verification_form'

export default function CheckEmailPage() {
  const { state } = useLocation()
  return (
    <EmailVerificationLayout>
      <h1>Revisá tu correo</h1>
      <p role="status">Cuenta creada. Revisá tu email para validar la cuenta antes de iniciar sesión</p>
      <p>Si no encontrás el mensaje, revisá la carpeta de spam o solicitá otro enlace.</p>
      <ResendVerificationForm initialEmail={state?.email || ''} />
      <Link to="/login">Ir a Iniciar Sesión</Link>
    </EmailVerificationLayout>
  )
}
