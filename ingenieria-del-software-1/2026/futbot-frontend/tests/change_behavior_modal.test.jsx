import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ChangeBehaviorModal from '../src/components/change_behavior_modal'

const starters = [
  { id: 'p1', name: 'Ana', behavior_id: 'b1' },
  { id: 'p2', name: 'Beto', behavior_id: 'b1' },
  { id: 'p3', name: 'Caro' },
]
const behaviors = [
  { id: 'b1', name: 'Defensivo' },
  { id: 'b2', name: 'Ofensivo' },
]

function setup() {
  const on_confirm = vi.fn()
  const on_close = vi.fn()
  render(<ChangeBehaviorModal starters={starters} behaviors={behaviors} on_confirm={on_confirm} on_close={on_close} />)
  return { on_confirm, on_close }
}

describe('ChangeBehaviorModal', () => {
  it('muestra un select por cada titular', () => {
    setup()
    expect(screen.getAllByRole('combobox')).toHaveLength(3)
  })

  it('deshabilita Confirmar si no hay cambios', () => {
    setup()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
  })

  it('confirma solo los jugadores que cambiaron', () => {
    const { on_confirm } = setup()
    fireEvent.change(screen.getByLabelText('Comportamiento de Ana'), { target: { value: 'b2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(on_confirm).toHaveBeenCalledWith([{ playerId: 'p1', behaviorId: 'b2' }])
  })

  it('arranca en "Elegir…" si falta el comportamiento actual', () => {
    setup()
    expect(screen.getByLabelText('Comportamiento de Caro')).toHaveValue('')
  })

  it('Cancelar llama a on_close', () => {
    const { on_close } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(on_close).toHaveBeenCalled()
  })
})