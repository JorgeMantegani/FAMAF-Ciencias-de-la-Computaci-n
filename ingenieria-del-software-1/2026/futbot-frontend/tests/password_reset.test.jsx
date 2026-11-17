import { StrictMode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'

const reply = (body, status = 200) => new Response(JSON.stringify(body), { status })
const genericMessage = 'Si el correo está registrado, recibirás un enlace para restablecer tu contraseña en los próximos minutos.'

function mount(path) {
  window.history.replaceState(null, '', path)
  return render(<StrictMode><App /></StrictMode>)
}

function fillPasswords(password = 'new-password', confirmation = password) {
  fireEvent.change(screen.getByLabelText('Nueva contraseña'), { target: { value: password } })
  fireEvent.change(screen.getByLabelText('Confirmar nueva contraseña'), { target: { value: confirmation } })
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

describe('Solicitud de recuperación', () => {
  it('permite navegar desde el login y volver', async () => {
    const user = userEvent.setup()
    mount('/login')
    await user.click(screen.getByRole('link', { name: '¿Olvidaste tu contraseña?' }))
    expect(window.location.pathname).toBe('/forgot-password')
    expect(screen.getByRole('heading', { name: 'Recuperar contraseña' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Volver a Iniciar Sesión' }))
    expect(window.location.pathname).toBe('/login')
  })

  it('rechaza emails vacíos o inválidos sin enviar peticiones', () => {
    mount('/forgot-password')
    const button = screen.getByRole('button', { name: 'Enviar enlace de recuperación' })
    fireEvent.click(button)
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'incorrecto' } })
    fireEvent.click(button)
    expect(fetch).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it.each(['registered@example.com', 'missing@example.com'])(
    'muestra la misma confirmación genérica para %s', async (email) => {
      fetch.mockResolvedValueOnce(reply({ detail: 'Si corresponde, recibirás un correo.' }))
      mount('/forgot-password')
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } })
      fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace de recuperación' }))
      expect(await screen.findByRole('status')).toHaveTextContent(genericMessage)
      expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
      const [url, options] = fetch.mock.calls[0]
      expect(url).toMatch(/\/api\/auth\/forgot-password$/)
      expect(options.method).toBe('POST')
      expect(JSON.parse(options.body)).toEqual({ email })
      expect(options.headers.has('Authorization')).toBe(false)
      expect(localStorage.length).toBe(0)
      expect(sessionStorage.length).toBe(0)
    },
  )

  it('bloquea duplicados durante el envío y permite reintentar un fallo de red', async () => {
    let reject
    fetch.mockReturnValueOnce(new Promise((resolve, fail) => { reject = fail }))
    mount('/forgot-password')
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    const button = screen.getByRole('button', { name: 'Enviar enlace de recuperación' })
    fireEvent.click(button)
    fireEvent.submit(button.closest('form'))
    expect(button).toBeDisabled()
    expect(screen.getByLabelText('Email')).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(1)
    reject(new TypeError('Failed to fetch'))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    fetch.mockResolvedValueOnce(reply({}))
    fireEvent.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent(genericMessage)
  })

  it('no muestra una confirmación falsa ante un error del servidor', async () => {
    fetch.mockResolvedValueOnce(reply({ detail: 'Error interno' }, 500))
    mount('/forgot-password')
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace de recuperación' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo solicitar el enlace')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('Restablecimiento', () => {
  it.each(['/reset-password', '/reset-password?token=', '/reset-password?token=%20'])(
    'informa de inmediato si falta el token en %s', async (path) => {
      mount(path)
      expect(screen.getByRole('alert')).toHaveTextContent('no contiene un token')
      expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument()
      expect(fetch).not.toHaveBeenCalled()
      await userEvent.click(screen.getByRole('link', { name: 'Solicitar nuevo enlace' }))
      expect(window.location.pathname).toBe('/forgot-password')
    },
  )

  it('muestra advertencias y bloquea el envío hasta que las contraseñas cumplan la longitud y coincidan', () => {
    mount('/reset-password?token=abc')
    const button = screen.getByRole('button', { name: 'Actualizar contraseña' })
    expect(button).toBeDisabled()
    fillPasswords('short')
    expect(screen.getByRole('alert')).toHaveTextContent('entre 8 y 20')
    expect(button).toBeDisabled()
    fillPasswords('x'.repeat(21))
    expect(button).toBeDisabled()
    fillPasswords('new-password', 'different-password')
    expect(screen.getByRole('alert')).toHaveTextContent('Las contraseñas no coinciden')
    expect(button).toBeDisabled()
    fireEvent.submit(button.closest('form'))
    expect(fetch).not.toHaveBeenCalled()
    fillPasswords('new-password')
    expect(button).toBeEnabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('captura el token de la URL, evita duplicados, limpia la sesión y permite ir al login', async () => {
    const session = JSON.stringify({
      access_token: 'old-access', refresh_token: 'old-refresh', club_id: 'club',
      expires_at: Math.floor(Date.now() / 1000) + 3600,
    })
    localStorage.setItem('futbot.session', session)
    sessionStorage.setItem('futbot.session', session)
    let finish
    fetch.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
    mount('/reset-password?other=value&token=abc%2B123')
    expect(fetch).not.toHaveBeenCalled()
    fillPasswords(' new-password ')
    const button = screen.getByRole('button', { name: 'Actualizar contraseña' })
    fireEvent.click(button)
    fireEvent.submit(button.closest('form'))
    expect(button).toBeDisabled()
    expect(screen.getByLabelText('Nueva contraseña')).toBeDisabled()
    expect(screen.getByLabelText('Confirmar nueva contraseña')).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, options] = fetch.mock.calls[0]
    expect(url).toMatch(/\/api\/auth\/reset-password$/)
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ token: 'abc+123', newPassword: ' new-password ' })
    expect(options.headers.has('Authorization')).toBe(false)
    expect(localStorage.getItem('futbot.session')).toBe(session)
    finish(reply({ detail: 'Contraseña actualizada.' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Contraseña actualizada correctamente')
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(window.location.pathname).toBe('/reset-password')
    await userEvent.click(screen.getByRole('link', { name: 'Ir a Iniciar Sesión' }))
    expect(window.location.pathname).toBe('/login')
    expect(screen.getByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument()
  })

  it.each(['PASSWORD_RESET_TOKEN_INVALID', 'PASSWORD_RESET_TOKEN_EXPIRED'])(
    'muestra el error de enlace y permite solicitar otro ante %s', async (error_code) => {
      fetch.mockResolvedValueOnce(reply({ detail: 'Error del backend', error_code }, 400))
      mount('/reset-password?token=bad')
      fillPasswords()
      fireEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('El enlace de recuperación ha caducado o es inválido')
      expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('link', { name: 'Solicitar nuevo enlace' }))
      expect(window.location.pathname).toBe('/forgot-password')
    },
  )

  it('permite reintentar un fallo de red sin guardar el token ni la contraseña', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    mount('/reset-password?token=private-token')
    fillPasswords()
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    fetch.mockResolvedValueOnce(reply({}))
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Contraseña actualizada correctamente')
  })

  it('conserva el resultado exitoso si el navegador impide limpiar la sesión', async () => {
    fetch.mockResolvedValueOnce(reply({}))
    mount('/reset-password?token=abc')
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('Storage blocked') })
    fillPasswords()
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Contraseña actualizada correctamente'))
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo limpiar la sesión')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
