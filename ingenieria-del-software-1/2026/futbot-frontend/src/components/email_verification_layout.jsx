import { Link } from 'react-router-dom'
import '../pages/email_verification.css'

export default function EmailVerificationLayout({ children }) {
  return (
    <div className="email-page">
      <header><Link to="/">⚽ FutBot</Link></header>
      <main className="email-card">{children}</main>
    </div>
  )
}
