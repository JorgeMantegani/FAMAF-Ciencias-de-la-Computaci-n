import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api/client'
import { read_session, save_session } from '../auth/session'
import './Login.css'

export default function Login() {
  const [email, set_email] = useState('')
  const [password, set_password] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [error, set_error] = useState('')
  const [status, set_status] = useState('idle')
  const submitting = useRef(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (read_session()) navigate('/home', { replace: true })
  }, [navigate])

  useEffect(() => {
    if (status !== 'success') return
    const timer = setTimeout(() => navigate('/home', { replace: true }), 1000)
    return () => clearTimeout(timer)
  }, [status, navigate])

  async function handle_submit(event) {
    event.preventDefault()
    if (submitting.current || !event.currentTarget.reportValidity()) return
    submitting.current = true
    set_error('')
    set_status('loading')
    try {
      const session = await login({ email, password })
      save_session(session, remember)
      set_password('')
      set_status('success')
    } catch (cause) {
      set_error(cause.status === 401
        ? `Credenciales inválidas.${cause.message && cause.message !== 'Credenciales inválidas' ? ` ${cause.message}` : ''}`
        : cause.status
          ? cause.message
          : cause instanceof TypeError
            ? 'No se pudo conectar con el servidor. Intentá nuevamente.'
            : cause.message || 'No se pudo iniciar sesión. Intentá nuevamente.')
      set_status('idle')
      submitting.current = false
    }
  }

  const busy = status !== 'idle'
  return (
    <div className="login-page">
      <header className="login-topbar">
        <Link className="login-identity" to="/" aria-label="FutBot, inicio">
          <span className="login-mark" aria-hidden="true">⚽</span>
          <span><span className="login-product">FutBot</span><span className="login-project">laboratorio / presión alta v4</span></span>
        </Link>
        <span className="login-availability"><i aria-hidden="true" /> Club abierto</span>
      </header>
      <main className="login-access">
        <div className="login-panel">
          <section className="login-tactics" aria-label="Plan de partido ilustrativo">
            <svg className="login-pitch" viewBox="0 0 560 650" fill="none" aria-hidden="true">
              <g stroke="#f3ecdd" strokeOpacity=".45" strokeWidth="2">
                <path d="M52 44h456v562H52zM52 325h456M165 44v82h230V44M165 606v-82h230v82" />
                <circle cx="280" cy="325" r="60" />
              </g>
              <circle cx="280" cy="325" r="4" fill="#f3ecdd" opacity=".65" />
              {[[8, 167, 366], [9, 393, 373], [10, 279, 435], [1, 279, 524]].map(([number, x, y]) => (
                <g key={number}>
                  <circle cx={x} cy={y} r="21" fill={number === 1 ? '#0b2a16' : '#d49a53'} stroke={number === 1 ? '#f3ecdd' : '#7e522a'} strokeWidth={number === 1 ? 2 : 3} />
                  <text x={x} y={y} dy=".35em" textAnchor="middle" fill="white" stroke="none" fontSize="12" fontWeight="700">{number}</text>
                </g>
              ))}
            </svg>
            <div className="login-tactics-heading">
              <p className="login-eyebrow"><span aria-hidden="true">—</span> Plan de partido</p>
              <h2>Diseña la próxima jugada.</h2>
              <p>Tu sistema, tu presión y cada decisión del equipo en un solo lugar.</p>
            </div>
            <dl className="login-metrics">
              {[['4-3-3', 'Sistema'], ['ALTA', 'Presión'], ['+12%', 'Rendimiento']].map(([value, label]) => (
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              ))}
            </dl>
          </section>
          <section className="login-form-panel" aria-labelledby="login-title">
            <div>
              <div className="login-heading">
                <p className="login-eyebrow"><LoginIcon kind="shield" /> Acceso al vestuario</p>
                <h1 id="login-title">Iniciar sesión</h1>
                <p>Ingresá a tu cuenta para gestionar tu club y preparar la próxima jugada.</p>
              </div>
              <form onSubmit={handle_submit} aria-busy={status === 'loading'}>
                <div className="login-field">
                  <label htmlFor="email">Email</label>
                  <div className="login-input">
                    <LoginIcon kind="user" />
                    <input id="email" name="email" type="email" autoComplete="username" placeholder="nombre@club.com"
                      required value={email} onChange={(event) => set_email(event.target.value)} disabled={busy} />
                  </div>
                </div>
                <div className="login-field">
                  <label htmlFor="password">Contraseña</label>
                  <div className="login-input">
                    <LoginIcon kind="lock" />
                    <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Ingresá tu contraseña"
                      required value={password} onChange={(event) => set_password(event.target.value)} disabled={busy} />
                    <button className="login-password-toggle" type="button" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword}
                      onClick={() => setShowPassword(!showPassword)} disabled={busy}><LoginIcon kind={showPassword ? 'eye' : 'eye-off'} /></button>
                  </div>
                </div>
                <label className="login-remember"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} disabled={busy} /> Recordarme</label>
                {error && <p className="login-message login-error" role="alert">{error}</p>}
                {status === 'success' && <p className="login-message login-success" role="status">Sesión iniciada correctamente. Redirigiendo al menú principal…</p>}
                <button className="login-submit" type="submit" disabled={busy}>
                  {status === 'loading' ? 'Iniciando sesión…' : status === 'success' ? 'Sesión iniciada' : 'Iniciar sesión'}
                  <LoginIcon kind="arrow" />
                </button>
              </form>
            </div>
            <footer className="login-footer">
              <p>¿No tenés cuenta? <Link to="/register">Crear cuenta</Link></p>
              <p className="login-security"><LoginIcon kind="shield" /> Tu estrategia empieza en tu club.</p>
            </footer>
          </section>
        </div>
      </main>
    </div>
  )
}

function LoginIcon({ kind }) {
  const paths = {
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M9 12l2 2 4-4',
    user: 'M20 21v-2a7 7 0 0 0-14 0v2 M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
    lock: 'M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0 M12 14v3',
    eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
    'eye-off': 'M3 3l18 18 M10 5c7-1 12 7 12 7s-1 2-3 4 M6 6c-3 2-4 6-4 6s4 7 10 7c2 0 3 0 5-2 M10 10a3 3 0 0 0 4 4',
    arrow: 'M5 12h14 M13 6l6 6-6 6',
  }
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[kind]} /></svg>
}
