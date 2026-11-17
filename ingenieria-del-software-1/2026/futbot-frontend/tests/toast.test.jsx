import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import Toast from '../src/components/toast'

beforeEach(() => vi.useFakeTimers())
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('Toast', () => {
  it('muestra el mensaje como status si es de éxito', () => {
    render(<Toast message="Listo" on_close={() => { }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Listo')
  })

  it('muestra el mensaje como alert si es de error', () => {
    render(<Toast message="Falló" type="error" on_close={() => { }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Falló')
  })

  it('se cierra solo a los 4 segundos', () => {
    const on_close = vi.fn()
    render(<Toast message="Listo" on_close={on_close} />)
    act(() => { vi.advanceTimersByTime(3999) })
    expect(on_close).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(1) })
    expect(on_close).toHaveBeenCalledTimes(1)
  })

  it('se cierra con la ×', () => {
    const on_close = vi.fn()
    render(<Toast message="Listo" on_close={on_close} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar aviso' }))
    expect(on_close).toHaveBeenCalledTimes(1)
  })
})