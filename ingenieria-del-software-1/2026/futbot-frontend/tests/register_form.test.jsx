import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RegisterForm from '../src/components/register_form';
import * as authApi from '../src/api/auth';
import { BrowserRouter } from 'react-router-dom';

// Simulamos la función de la API y el useNavigate de React Router
vi.mock('../src/api/auth', () => ({
  registerUser: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('RegisterForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Renderiza el componente dentro del Router (porque usa useNavigate)
  const renderComponent = () => {
    render(
      <BrowserRouter>
        <RegisterForm />
      </BrowserRouter>
    );
  };

  it('Debe renderizar todos los campos del formulario', () => {
    renderComponent();
    expect(screen.getByLabelText(/Nombre de usuario/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Correo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nombre del Club/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contraseña/i)).toBeInTheDocument();
  });

  it('Debe mantener el botón deshabilitado si el email es inválido', async () => {
    const user = userEvent.setup();
    renderComponent();
    
    const submitButton = screen.getByRole('button', { name: /CREAR MI CUENTA/i });
    
    // Cuando cargo la pagina debe estar deshabilitado el boton
    expect(submitButton).toBeDisabled();

    // Agregamos datos válidos excepto el email
    await user.type(screen.getByLabelText(/Nombre de usuario/i), 'Transistores');
    await user.type(screen.getByLabelText(/Correo/i), 'correo-invalido');
    await user.type(screen.getByLabelText(/Nombre del Club/i), 'Los Transistores FC');
    await user.type(screen.getByLabelText(/Contraseña/i), '12345678');

    // El boton deberia estar deshabilitado porque el mail no es valido
    expect(submitButton).toBeDisabled();
  });

  it('Debe mantener el botón deshabilitado si faltan datos', async () => {
    const user = userEvent.setup();
    renderComponent();
    
    const submitButton = screen.getByRole('button', { name: /CREAR MI CUENTA/i });
    
    // Cuando cargo la pagina debe estar deshabilitado el boton
    expect(submitButton).toBeDisabled();

    // Agrego datos y verifico
    await user.type(screen.getByLabelText(/Nombre de usuario/i), 'Transistores');
    expect(submitButton).toBeDisabled();
    await user.type(screen.getByLabelText(/Correo/i), 'grupoTransistores@mail.com');
    expect(submitButton).toBeDisabled();
    await user.type(screen.getByLabelText(/Nombre del Club/i), 'Los Transistores FC');
    expect(submitButton).toBeDisabled();
    await user.type(screen.getByLabelText(/Contraseña/i), '12345678');

    // Ahora que completamos todos los campos, el boton deberia estar habilitado
    expect(submitButton).not.toBeDisabled();

  });

  it('Debe actualizar el avatar seleccionado y enviarlo al backend', async () => {
    const user = userEvent.setup();
    authApi.registerUser.mockResolvedValueOnce({ id: 1, message: 'OK' });

    renderComponent();

    // Busca la imagen del Avatar 5 y la clickea
    const avatar5 = screen.getByAltText('Avatar 5');
    await user.click(avatar5);

    // Llena el resto de los datos válidos para que se habilite el botón
    await user.type(screen.getByLabelText(/Nombre de usuario/i), 'Transistores');
    await user.type(screen.getByLabelText(/Correo/i), 'Transistores@mail.com');
    await user.type(screen.getByLabelText(/Nombre del Club/i), 'Los Transistores FC');
    await user.type(screen.getByLabelText(/Contraseña/i), '12345678');

    // Envia el formulario
    const submitButton = screen.getByRole('button', { name: /CREAR MI CUENTA/i });
    await user.click(submitButton);

    // Verifica que la función de la API recibió '5' en lugar del '1' por defecto
    expect(authApi.registerUser).toHaveBeenCalledWith(
      expect.objectContaining({
        avatar: '5'
      })
    );
  });

  it('Debe enviar el payload correcto y mostrar mensaje de éxito (201)', async () => {
    const user = userEvent.setup();
    authApi.registerUser.mockResolvedValueOnce({ id: 1, message: 'OK' });

    renderComponent();

    await user.type(screen.getByLabelText(/Nombre de usuario/i), 'Transistores');
    await user.type(screen.getByLabelText(/Correo/i), 'grupoTransistores@mail.com');
    await user.type(screen.getByLabelText(/Nombre del Club/i), 'Los Transistores FC');
    await user.type(screen.getByLabelText(/Contraseña/i), '12345678');

    const submitButton = screen.getByRole('button', { name: /CREAR MI CUENTA/i });
    expect(submitButton).not.toBeDisabled();

    await user.click(submitButton);

    // Verifica que se llamó a la API con los datos correctos y el avatar '1' por defecto
    expect(authApi.registerUser).toHaveBeenCalledWith({
      username: 'Transistores',
      email: 'grupoTransistores@mail.com',
      clubName: 'Los Transistores FC',
      password: '12345678',
      avatar: '1',
    });

    // Verifica que aparezca el mensaje de éxito en pantalla
    expect(await screen.findByText(/Usuario registrado correctamente/i)).toBeInTheDocument();
  });

  it('Debe mostrar mensaje de error si el backend falla (Simula 400)', async () => {
    const user = userEvent.setup();
    // La API lanza el error 400
    authApi.registerUser.mockRejectedValueOnce(new Error('El correo ya está registrado'));

    renderComponent();

    await user.type(screen.getByLabelText(/Nombre de usuario/i), 'Transistores');
    await user.type(screen.getByLabelText(/Correo/i), 'duplicado@mail.com');
    await user.type(screen.getByLabelText(/Nombre del Club/i), 'Los Transistores FC');
    await user.type(screen.getByLabelText(/Contraseña/i), '12345678');

    await user.click(screen.getByRole('button', { name: /CREAR MI CUENTA/i }));

    // Verifica que el error capturado del backend se renderice en pantalla
    expect(await screen.findByText(/El correo ya está registrado/i)).toBeInTheDocument();
  });
});