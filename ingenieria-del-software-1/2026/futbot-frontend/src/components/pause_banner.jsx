import { useEffect, useId, useState } from 'react'
import './pause_banner.css'

const PAUSE_LABELS = { HYDRATION: 'Pausa de hidratación', HALFTIME: 'Entretiempo' }
const REFRESH_MS = 250

const is_seconds = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0

export default function PauseBanner({ phase, pause_duration, pause_remaining }) {
  const title_id = useId()
  // Read once per pause: later snapshots must not re-anchor the countdown.
  const [initial_seconds] = useState(() => is_seconds(pause_remaining) ? pause_remaining : is_seconds(pause_duration) ? pause_duration : null)
  const [seconds_left, set_seconds_left] = useState(() => initial_seconds === null ? null : Math.ceil(initial_seconds))

  useEffect(() => {
    if (initial_seconds === null) return undefined
    const started_at = performance.now()
    // Derived from elapsed time so a throttled interval in a background tab does not drift.
    const interval = setInterval(() => {
      const left = Math.max(0, Math.ceil(initial_seconds - (performance.now() - started_at) / 1000))
      set_seconds_left(left)
      if (left === 0) clearInterval(interval)
    }, REFRESH_MS)
    return () => clearInterval(interval)
  }, [initial_seconds])

  return (
    <section className="fb-pause-banner" aria-labelledby={title_id}>
      <p id={title_id} className="fb-pause-banner__title">{PAUSE_LABELS[phase] ?? 'En pausa'}</p>
      {seconds_left !== null && (
        <p className="fb-pause-banner__countdown">
          Se reanuda en <time className="fb-pause-banner__seconds" aria-label="Tiempo restante de la pausa" dateTime={`PT${seconds_left}S`}>{seconds_left} s</time>
        </p>
      )}
    </section>
  )
}
