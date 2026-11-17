import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PauseBanner from '../src/components/pause_banner'

const paused_tick = (changes = {}) => ({ status: 'paused', phase: 'HYDRATION', pause_duration: 15, pause_remaining: 15, ...changes })
const banner = (tick) => <PauseBanner phase={tick.phase} pause_duration={tick.pause_duration} pause_remaining={tick.pause_remaining} />
const countdown = () => screen.getByLabelText('Tiempo restante de la pausa')
const advance = async (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('PauseBanner', () => {
  it('muestra la pausa de hidratación con la duración exacta del backend', () => {
    render(banner(paused_tick()))
    expect(screen.getByRole('region', { name: 'Pausa de hidratación' })).toBeInTheDocument()
    expect(countdown()).toHaveTextContent('15 s')
  })

  it('muestra el entretiempo con su duración', () => {
    render(banner(paused_tick({ phase: 'HALFTIME', pause_duration: 20, pause_remaining: 20 })))
    expect(screen.getByRole('region', { name: 'Entretiempo' })).toBeInTheDocument()
    expect(countdown()).toHaveTextContent('20 s')
  })

  it('arranca en el tiempo restante, redondeado hacia arriba, al entrar a mitad de la pausa', async () => {
    render(banner(paused_tick({ pause_remaining: 4.6 })))
    expect(countdown()).toHaveTextContent('5 s')
    await advance(1000)
    expect(countdown()).toHaveTextContent('4 s')
  })

  it('usa la duración total si no llega el tiempo restante', () => {
    render(banner(paused_tick({ pause_remaining: undefined })))
    expect(countdown()).toHaveTextContent('15 s')
  })

  it('descuenta con el reloj y se detiene en 0', async () => {
    render(banner(paused_tick()))
    await advance(1000)
    expect(countdown()).toHaveTextContent('14 s')
    await advance(5000)
    expect(countdown()).toHaveTextContent('9 s')
    await advance(20000)
    expect(countdown()).toHaveTextContent('0 s')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('no reajusta la cuenta con los snapshots siguientes de la misma pausa', async () => {
    const view = render(banner(paused_tick()))
    await advance(3000)
    view.rerender(banner(paused_tick({ pause_remaining: 14 })))
    await advance(250)
    expect(countdown()).toHaveTextContent('12 s')
  })

  it('muestra "En pausa" sin cuenta regresiva ante una fase desconocida', () => {
    render(banner(paused_tick({ phase: 'PENALTIES', pause_duration: null, pause_remaining: null })))
    expect(screen.getByRole('region', { name: 'En pausa' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Tiempo restante de la pausa')).not.toBeInTheDocument()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('limpia el temporizador al desmontarse', () => {
    const view = render(banner(paused_tick()))
    expect(vi.getTimerCount()).toBe(1)
    view.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
