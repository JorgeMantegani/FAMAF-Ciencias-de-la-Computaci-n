import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CreatePlayerForm from '../src/components/create_player_form.jsx';
import * as playersApi from '../src/api/players.js';

// Mock de createPlayer para evitar llamadas reales a la API
vi.mock('../src/api/players.js', () => ({ createPlayer: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
});

const ATTRS = [/Power/i, /Agility/i, /Control/i, /Speed/i, /Strength/i];

// Llenar el formulario con un nombre y un array de valores para los atributos
async function fill_form(user, name, values) {
  if (name) {
    await user.type(screen.getByLabelText(/Nombre/i), name);
  }

  for (let i = 0; i < ATTRS.length; i++) {
    await user.type(screen.getByLabelText(ATTRS[i]), values[i]);
  }
}

// Tests para el componente CreatePlayerForm
describe('CreatePlayerForm', () => {
  it('Debe renderizar el nombre y los cinco atributos', () => {
    render(<CreatePlayerForm />);

    expect(screen.getByLabelText(/Nombre/i)).toBeInTheDocument();

    ATTRS.forEach((attr) => {
      expect(screen.getByLabelText(attr)).toBeInTheDocument();
    });
  });

  it('Debe arrancar con el botón Crear deshabilitado y sin errores visibles', () => {
    render(<CreatePlayerForm />);

    expect(
      screen.getByRole('button', { name: /Crear/i })
    ).toBeDisabled();

    expect(screen.queryByText(/obligatorio/i)).not.toBeInTheDocument();
  });

  it('Debe mostrar el error de un campo recién después de tocarlo', async () => {
    const user = userEvent.setup();

    render(<CreatePlayerForm />);

    await user.click(screen.getByLabelText(/Nombre/i));
    await user.tab();

    expect(
      screen.getByText(/nombre es obligatorio/i)
    ).toBeInTheDocument();
  });

  it('No debe permitir caracteres no numéricos en los atributos', async () => {
    const user = userEvent.setup();

    render(<CreatePlayerForm />);

    const power = screen.getByLabelText(/Power/i);

    await user.type(power, 'a1b2');

    expect(power).toHaveValue('12');
  });

  // Validaciones de la interfaz
  describe('validaciones del formulario', () => {
    it('Debe mantener el botón deshabilitado con un nombre de menos de 3 caracteres', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Jo', ['60', '60', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();
    });

    it('Debe mantener el botón deshabilitado con un atributo menor a 20', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['19', '61', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();
    });

    it('Debe mantener el botón deshabilitado con un atributo mayor a 100', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['101', '49', '50', '50', '50']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();
    });

    it('Debe mantener el botón deshabilitado si la suma no es 300', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['59', '60', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();

      expect(
        screen.getByText(/exactamente 300/i)
      ).toBeInTheDocument();
    });

    it('Debe habilitar el botón con datos válidos y suma 300', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['60', '60', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeEnabled();
    });

    it('Debe mostrar la suma parcial mientras se completan los atributos', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await user.type(screen.getByLabelText(/Power/i), '50');
      await user.type(screen.getByLabelText(/Agility/i), '40');

      expect(
        screen.getByText('Suma: 90 / 300')
      ).toBeInTheDocument();
    });
  });

  // Verifica que los datos inválidos no lleguen a la API
  describe('prevención de envío con datos inválidos', () => {
    it('No debe llamar a createPlayer con un nombre menor a 3 caracteres', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Jo', ['60', '60', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();

      expect(playersApi.createPlayer).not.toHaveBeenCalled();
    });

    it('No debe llamar a createPlayer con un atributo menor a 20', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['19', '61', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();

      expect(playersApi.createPlayer).not.toHaveBeenCalled();
    });

    it('No debe llamar a createPlayer con un atributo mayor a 100', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['101', '49', '50', '50', '50']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();

      expect(playersApi.createPlayer).not.toHaveBeenCalled();
    });

    it('No debe llamar a createPlayer si la suma no es 300', async () => {
      const user = userEvent.setup();

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', ['59', '60', '60', '60', '60']);

      expect(
        screen.getByRole('button', { name: /Crear/i })
      ).toBeDisabled();

      expect(playersApi.createPlayer).not.toHaveBeenCalled();
    });
  });

  it('Debe llamar a onCancel al presionar Cancelar', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(<CreatePlayerForm onCancel={onCancel} />);

    await user.click(
      screen.getByRole('button', { name: /Cancelar/i })
    );

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  describe('envío', () => {
    const VALID = ['60', '60', '60', '60', '60'];

    it('Debe llamar a createPlayer con los datos y luego a onSuccess', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();

      playersApi.createPlayer.mockResolvedValueOnce({});

      render(<CreatePlayerForm onSuccess={onSuccess} />);

      await fill_form(user, 'Messi', VALID);

      await user.click(
        screen.getByRole('button', { name: /Crear/i })
      );

      expect(playersApi.createPlayer).toHaveBeenCalledWith({
        name: 'Messi',
        power: '60',
        agility: '60',
        control: '60',
        speed: '60',
        strength: '60',
      });

      await waitFor(() =>
        expect(onSuccess).toHaveBeenCalledTimes(1)
      );
    });

    it('Debe mostrar el error del servidor y no llamar a onSuccess', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();

      playersApi.createPlayer.mockRejectedValueOnce(
        new Error('Ya existe un jugador con ese nombre'),
      );

      render(<CreatePlayerForm onSuccess={onSuccess} />);

      await fill_form(user, 'Messi', VALID);

      await user.click(
        screen.getByRole('button', { name: /Crear/i })
      );

      expect(
        await screen.findByText(/Ya existe un jugador/i)
      ).toBeInTheDocument();

      expect(onSuccess).not.toHaveBeenCalled();
    });

    it('Debe deshabilitar el botón mientras se envía', async () => {
      const user = userEvent.setup();

      // Promesa que nunca se resuelve: simula un envío en curso
      playersApi.createPlayer.mockReturnValueOnce(
        new Promise(() => { }),
      );

      render(<CreatePlayerForm />);

      await fill_form(user, 'Messi', VALID);

      await user.click(
        screen.getByRole('button', { name: /Crear/i })
      );

      expect(
        screen.getByRole('button', { name: /Creando/i })
      ).toBeDisabled();
    });
  });
});
