import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import BehaviorEditorPage from '../src/pages/behavior_editor_page.jsx'
import * as api from '../src/api/behaviors.js'
import { ApiError } from '../src/api/client.js'

vi.mock ('../src/api/behaviors.js', () => ({
  get_behavior: vi.fn(),
  create_behavior: vi.fn(),
  update_behavior: vi.fn(),
}))

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }) => (
    <textarea
      aria-label="Editor de código Python"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}))

describe('BehaviorEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  it('Debe renderizar la vista de creacion si no hay behavior_id', () => {
    render(
      <MemoryRouter initialEntries={['/behaviors/create']}>
        <Routes>
          <Route path="/behaviors/create" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('+ Crear comportamiento')).toBeInTheDocument()
    // Verifico que el editor esté presente con el texto del mock
    expect(screen.getByLabelText('Editor de código Python')).toBeInTheDocument(
    
    )
  })

  it('Debe renderizar la vista de edición si hay behavior_id', async () => {
    const mockBehavior = { name: 'Test Behavior', code: 'print("Hello")' }
    api.get_behavior.mockResolvedValue(mockBehavior)
    render(
      <MemoryRouter initialEntries={['/behaviors/edit/1']}>
        <Routes>
          <Route path="/behaviors/edit/:behavior_id" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Editar comportamiento')).toBeInTheDocument()
    
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Behavior')).toBeInTheDocument()
      expect(screen.getByLabelText('Editor de código Python')).toHaveValue('print("Hello")')
    })
    expect(screen.getByText('Actualizar comportamiento')).toBeInTheDocument()
  })

  it('Debe bloquear el boton y mostrar "Guardando..." mientras se guarda', async () => {
    api.create_behavior.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({}), 100))) 
    render(
      <MemoryRouter initialEntries={['/behaviors/create']}>
        <Routes>
          <Route path="/behaviors/create" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    const inputName = screen.getByPlaceholderText('Ej: Presión alta')
    fireEvent.change(inputName, { target: { value: 'Nuevo Comportamiento' } }) 
    const editor = screen.getByLabelText('Editor de código Python')
    fireEvent.change(editor, { target: { value: 'print("Nuevo comportamiento")' } }) 
    const submitButton = screen.getByText('+ Crear comportamiento')
    fireEvent.click(submitButton)
    
    expect(screen.getByText('Guardando...')).toBeDisabled()
  })

  it('Debe mostrar mensaje de error de la API si falla el guardado', async () => {
    const error_message_be = "El uso de 'eval' no está permitido en el código del comportamiento."
    api.create_behavior.mockRejectedValue(new Error(error_message_be))
    render(
      <MemoryRouter initialEntries={['/behaviors/create']}>
        <Routes>
          <Route path="/behaviors/create" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    const inputName = screen.getByPlaceholderText('Ej: Presión alta')
    fireEvent.change(inputName, { target: { value: 'Nuevo Comportamiento' } }) 
    const editor = screen.getByLabelText('Editor de código Python')
    fireEvent.change(editor, { target: { value: 'print("Nuevo comportamiento")' } }) 
    const submitButton = screen.getByText('+ Crear comportamiento')
    fireEvent.click(submitButton)
    
    await waitFor(() => {
      expect(api.create_behavior).toHaveBeenCalled()
      expect(screen.getByText(error_message_be)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', {'name': '+ Crear comportamiento'})).toBeEnabled()
  })

  it('Debe actualizar por medio de PUT al guardar comportamiento existente', async () => {
    const mockBehavior = { name: 'Test Behavior', code: 'print("Hello")' }
    api.get_behavior.mockResolvedValue(mockBehavior)
    api.update_behavior.mockResolvedValue({})
    render(
      <MemoryRouter initialEntries={['/behaviors/edit/1']}>
        <Routes>
          <Route path="/behaviors/edit/:behavior_id" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Behavior')).toBeInTheDocument()
    })
    const inputName = screen.getByDisplayValue('Test Behavior')
    fireEvent.change(inputName, { target: { value: 'Updated Behavior' } })
    const inputCode = screen.getByLabelText('Editor de código Python')
    fireEvent.change(inputCode, { target: { value: 'print("Updated")' } })
    const submitButton = screen.getByText('Actualizar comportamiento')
    fireEvent.click(submitButton)
    await waitFor(() => {
      expect(api.update_behavior).toHaveBeenCalledWith('1', {
        name: 'Updated Behavior',
        code: 'print("Updated")'
      })
    })
    expect(api.update_behavior).toHaveBeenCalledTimes(1)
    expect(api.create_behavior).not.toHaveBeenCalled()
  })

  it('Debe mantener el boton Actualizar deshabilitado si no hay cambios', async () => {
    const mockBehavior = { name: 'Test Behavior', code: 'print("Hello")' }
    api.get_behavior.mockResolvedValue(mockBehavior)
    render(
      <MemoryRouter initialEntries={['/behaviors/edit/1']}>
        <Routes>
          <Route path="/behaviors/edit/:behavior_id" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Behavior')).toBeInTheDocument()
    })
    const submitButton = screen.getByText('Actualizar comportamiento')
    expect(submitButton).toBeDisabled()
  })

  it('Debe enviar el payload correcto al crear un comportamiento', async () => {
    api.create_behavior.mockResolvedValue({})
    render(
      <MemoryRouter initialEntries={['/behaviors/create']}>
        <Routes>
          <Route path="/behaviors/create" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    const inputName = screen.getByPlaceholderText('Ej: Presión alta')
    fireEvent.change(inputName, { target: { value: 'Nuevo Comportamiento' } })
    const editor = screen.getByLabelText('Editor de código Python')
    fireEvent.change(editor, { target: { value: 'print("Nuevo comportamiento")' } })
    const submitButton = screen.getByText('+ Crear comportamiento')
    fireEvent.click(submitButton)
    await waitFor(() => {
      expect(api.create_behavior).toHaveBeenCalledWith({
        name: 'Nuevo Comportamiento',
        code: 'print("Nuevo comportamiento")'
      })
    })
    expect(api.create_behavior).toHaveBeenCalledTimes(1)
    expect(api.update_behavior).not.toHaveBeenCalled()
  })
  it('Debe mostrar mensaje de error si recibe un error 422 de la API', async () => {
    const error_message_be = "El uso de 'eval' no está permitido en el código del comportamiento."
    api.create_behavior.mockRejectedValue(new ApiError(422, error_message_be))
    render(
      <MemoryRouter initialEntries={['/behaviors/create']}>
        <Routes>
          <Route path="/behaviors/create" element={<BehaviorEditorPage />} />
        </Routes>
      </MemoryRouter>
    )
    const inputName = screen.getByPlaceholderText('Ej: Presión alta')
    fireEvent.change(inputName, { target: { value: 'Nuevo Comportamiento' } })
    const editor = screen.getByLabelText('Editor de código Python')
    fireEvent.change(editor, { target: { value: 'print("Nuevo comportamiento")' } })
    const submitButton = screen.getByText('+ Crear comportamiento')
    fireEvent.click(submitButton)
    await waitFor(() => {
      expect(api.create_behavior).toHaveBeenCalled()
      expect(screen.getByText(error_message_be)).toBeInTheDocument()
    })
    expect(screen.getByPlaceholderText('Ej: Presión alta')).toHaveValue('Nuevo Comportamiento')
    expect(screen.getByLabelText('Editor de código Python')).toHaveValue('print("Nuevo comportamiento")')
  
  })
})