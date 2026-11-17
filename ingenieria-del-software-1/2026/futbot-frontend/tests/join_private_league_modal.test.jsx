import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import JoinPrivateLeagueModal from '../src/components/join_private_league_modal'
import { find_league_by_code } from '../src/api/leagues'

vi.mock('../src/api/leagues', () => ({ find_league_by_code: vi.fn() }))

const found_league = { leagueId: 'league-1', name: 'Liga Privada', isPrivate: true }

const api_error = (status, error_code) =>
  Object.assign(new Error('error del backend'), { status, error_code })

const on_close = vi.fn()
const on_found = vi.fn()

function mount() {
  const view = render(<JoinPrivateLeagueModal on_close={on_close} on_found={on_found} />)
  return { ...view, user: userEvent.setup() }
}

const code_field = () => screen.getByLabelText('Código de la liga')
const search_button = () => screen.getByRole('button', { name: 'Buscar liga' })

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true
  }
})

beforeEach(() => {
  vi.resetAllMocks()
})

describe('JoinPrivateLeagueModal', () => {
  it('opens with an empty code field', () => {
    mount()

    expect(screen.getByRole('dialog', { name: 'Unirse a liga privada' })).toBeInTheDocument()
    expect(code_field()).toHaveValue('')
  })

  it('asks for the code without calling the backend when it is empty', async () => {
    const { user } = mount()

    await user.type(code_field(), '   ')
    await user.click(search_button())

    expect(screen.getByRole('alert')).toHaveTextContent('Ingresá el código de la liga.')
    expect(find_league_by_code).not.toHaveBeenCalled()
  })

  it('searches with the code as typed, without edge spaces, and reports the league', async () => {
    find_league_by_code.mockResolvedValue(found_league)
    const { user } = mount()

    await user.type(code_field(), ' a1B2c3d4 ')
    await user.click(search_button())

    expect(find_league_by_code).toHaveBeenCalledWith('a1B2c3d4', {
      signal: expect.any(AbortSignal),
    })
    expect(on_found).toHaveBeenCalledWith(found_league)
  })

  it('does not call the backend with a code that has symbols', async () => {
    const { user } = mount()

    await user.type(code_field(), '..')
    await user.click(search_button())

    expect(screen.getByRole('alert')).toHaveTextContent('No hay ninguna liga con ese código.')
    expect(find_league_by_code).not.toHaveBeenCalled()
  })

  it('lets the user try another code after LEAGUE_NOT_FOUND', async () => {
    find_league_by_code.mockRejectedValueOnce(api_error(404, 'LEAGUE_NOT_FOUND'))
    find_league_by_code.mockResolvedValueOnce(found_league)
    const { user } = mount()

    await user.type(code_field(), 'malo1234')
    await user.click(search_button())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No hay ninguna liga con ese código. Revisalo e intentá de nuevo.'
    )
    expect(on_found).not.toHaveBeenCalled()

    await user.clear(code_field())
    await user.type(code_field(), 'a1b2c3d4')
    await user.click(search_button())

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(on_found).toHaveBeenCalledWith(found_league)
  })

  it.each([
    ['a network error', new TypeError('Failed to fetch'), 'No se pudo contactar al servidor.'],
    ['another backend error', api_error(500, 'INTERNAL_SERVER_ERROR'), 'No se pudo buscar la liga. Intentá nuevamente.'],
  ])('reports %s and lets the user retry', async (_, cause, message) => {
    find_league_by_code.mockRejectedValue(cause)
    const { user } = mount()

    await user.type(code_field(), 'a1b2c3d4')
    await user.click(search_button())

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(search_button()).toBeEnabled()
  })

  it('shows no error on a 401, because Home goes to the login', async () => {
    find_league_by_code.mockRejectedValue(api_error(401, 'UNAUTHORIZED'))
    const { user } = mount()

    await user.type(code_field(), 'a1b2c3d4')
    await user.click(search_button())

    expect(find_league_by_code).toHaveBeenCalled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(on_found).not.toHaveBeenCalled()
  })

  it('locks the form while searching and keeps the focus on the field', async () => {
    let respond
    find_league_by_code.mockReturnValue(new Promise((resolve) => { respond = resolve }))
    const { user } = mount()

    await user.type(code_field(), 'a1b2c3d4{Enter}')

    expect(screen.getByRole('button', { name: 'Buscando…' })).toBeDisabled()
    expect(code_field()).toHaveAttribute('readonly')
    expect(code_field()).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled()

    await user.keyboard('{Enter}')
    expect(find_league_by_code).toHaveBeenCalledTimes(1)

    await act(async () => respond(found_league))
    expect(on_found).toHaveBeenCalledTimes(1)
  })

  it('Cancelar asks to close the modal', async () => {
    const { user } = mount()

    await user.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(on_close).toHaveBeenCalled()
    expect(on_found).not.toHaveBeenCalled()
  })

  it('closing while searching cancels the request and ignores its answer', async () => {
    let respond
    find_league_by_code.mockReturnValue(new Promise((resolve) => { respond = resolve }))
    const { user, unmount } = mount()

    await user.type(code_field(), 'a1b2c3d4')
    await user.click(search_button())
    const { signal } = find_league_by_code.mock.calls[0][1]
    expect(signal.aborted).toBe(false)

    unmount()
    await act(async () => respond(found_league))

    expect(signal.aborted).toBe(true)
    expect(on_found).not.toHaveBeenCalled()
  })
})
