import { StrictMode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import VerifyEmailPage from '../src/pages/verify_email_page'
import CheckEmailPage from '../src/pages/check_email_page'
import Login from '../src/pages/Login'

const reply = (body, status = 200) => new Response(JSON.stringify(body), { status })
function mount(path, element) {
  return render(<StrictMode><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/verify-email" element={element || <VerifyEmailPage />} />
    <Route path="/check-email" element={<CheckEmailPage />} />
    <Route path="/login" element={<Login />} />
  </Routes></MemoryRouter></StrictMode>)
}
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('Verificación por correo', () => {
  it('extrae el token, envía una sola petición en StrictMode y permite ir al login', async () => {
    let finish
    fetch.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    mount('/verify-email?token=abc%2B123&other=value')
    expect(screen.getByRole('status')).toHaveTextContent('Validando')
    expect(screen.queryByRole('link', { name: 'Ir a Iniciar Sesión' })).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, options] = fetch.mock.calls[0]
    expect(url).toMatch(/\/api\/auth\/verify-email$/)
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ token: 'abc+123' })
    expect(options.headers.has('Authorization')).toBe(false)
    finish(reply({ detail: 'Correo verificado.' }))
    expect(await screen.findByText(/Tu correo fue verificado/)).toBeInTheDocument()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    fireEvent.click(screen.getByRole('link', { name: 'Ir a Iniciar Sesión' }))
    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument()
  })

  it.each(['EMAIL_VERIFICATION_TOKEN_INVALID', 'EMAIL_VERIFICATION_TOKEN_EXPIRED'])(
    'muestra el error %s y permite solicitar un enlace', async (code) => {
      fetch.mockResolvedValueOnce(reply({ detail: 'El enlace es inválido o venció.', error_code: code }, 400))
      mount('/verify-email?token=bad')
      expect(await screen.findByRole('alert')).toHaveTextContent('El enlace es inválido o venció.')
      fetch.mockResolvedValueOnce(reply({ detail: 'Si corresponde, recibirás un correo de verificación.' }))
      fireEvent.change(screen.getByLabelText('Email para recibir el enlace'), { target: { value: 'user@example.com' } })
      fireEvent.click(screen.getByRole('button', { name: 'Solicitar nuevo enlace' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Si corresponde')
      expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ email: 'user@example.com' })
      expect(fetch.mock.calls[1][0]).toMatch(/\/api\/auth\/resend-verification$/)
    },
  )

  it('no envía peticiones si falta el token', () => {
    mount('/verify-email')
    expect(screen.getByRole('alert')).toHaveTextContent('no contiene un token')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('informa un fallo de red', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    mount('/verify-email?token=abc')
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar')
  })

  it('muestra el aviso de cuenta creada y permite reenviar sin datos de navegación', () => {
    mount('/check-email')
    expect(screen.getByRole('status')).toHaveTextContent('Cuenta creada. Revisá tu email')
    expect(screen.getByLabelText('Email para recibir el enlace')).toHaveValue('')
  })

  it('interpreta EMAIL_NOT_VERIFIED en login y ofrece reenviar al email utilizado', async () => {
    fetch.mockResolvedValueOnce(reply({ detail: 'Debés verificar tu correo.', error_code: 'EMAIL_NOT_VERIFIED' }, 403))
    mount('/login')
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Debés validar tu email antes de iniciar sesión')
    expect(screen.getByLabelText('Email para recibir el enlace')).toHaveValue('user@example.com')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    let finish
    fetch.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
    const button = screen.getByRole('button', { name: 'Solicitar nuevo enlace' })
    fireEvent.click(button)
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(fetch).toHaveBeenCalledTimes(2)
    finish(reply({ detail: 'Si corresponde, recibirás un correo de verificación.' }))
    await waitFor(() => expect(button).toBeEnabled())
  })
})
