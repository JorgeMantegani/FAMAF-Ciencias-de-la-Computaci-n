import { describe, it, expect, beforeEach, afterEach,vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import BehaviorPage from '../src/pages/behavior_page.jsx'
import * as sessionModule from '../src/auth/session'
import * as apiModule from '../src/api/behaviors'
import userEvent from '@testing-library/user-event';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

vi.mock('../src/api/behaviors', () => ({
    get_behaviors: vi.fn(),
}));

vi.mock('../src/auth/session', () => ({
    read_session: vi.fn(),
}));

describe('BehaviorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {}); // Silencio de errores en la consola durante las pruebas
  });
  afterEach(() => {
  vi.restoreAllMocks()
  })

  it('Debe redirigir a /login si no hay sesión', () => {
    vi.mocked(sessionModule.read_session).mockReturnValue(null);
    render(<BehaviorPage />);
    expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
    expect(apiModule.get_behaviors).not.toHaveBeenCalled(); // no se llama a la api
    });

  it('Muestra el estado de carga inicialmente', () => {
    vi.mocked(sessionModule.read_session).mockReturnValue({
      access_token: 'fake-token',
    })

    vi.mocked(apiModule.get_behaviors).mockImplementation(
      () => new Promise(() => {})
    )
    render(<BehaviorPage />)
    expect(screen.getByText(/CARGANDO TÁCTICAS.../i)).toBeInTheDocument()
    expect(screen.queryByText('Comportamientos')).not.toBeInTheDocument()
  })

  it('Debe mostrar un mensaje de error si la API devuelve un error', async () => {
    vi.mocked(sessionModule.read_session).mockReturnValue({ access_token: 'fake-token' });
    vi.mocked(apiModule.get_behaviors).mockRejectedValue(new Error('500'));

    render(<BehaviorPage />);
    expect(apiModule.get_behaviors).toHaveBeenCalledTimes(1); // se hizo una unica petición a la API
    expect(await screen.findByText(/Error al obtener los comportamientos/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reintentar/i })).toBeInTheDocument();
    expect(screen.queryByText(/CARGANDO TÁCTICAS/i)).not.toBeInTheDocument(); // ya no está cargando
  })

  it('Debe mostrar la lista de comportamientos si la API responde correctamente', async () => {
    const mockBehaviors = [
      { id: 1, name: 'Comportamiento 1', code: 'C1', isDefault: true },
      { id: 2, name: 'Comportamiento 2', code: 'C2', isDefault: false },
    ];
    vi.mocked(sessionModule.read_session).mockReturnValue({
        access_token: 'fake-token',
    });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue(mockBehaviors);
    render(<BehaviorPage/>);
    expect(apiModule.get_behaviors).toHaveBeenCalledTimes(1); // se hizo una unica petición a la API
    expect(await screen.findByText('Comportamiento 1')).toBeInTheDocument();
    expect(screen.getByText('Comportamiento 2')).toBeInTheDocument();
    expect(screen.getByText('Preprogramado')).toBeInTheDocument();
    expect(screen.getByText('Propio')).toBeInTheDocument();
    expect(screen.queryByText(/Error al obtener/i)).not.toBeInTheDocument(); // no muestra error
  })
  
  it('Debe mostrar la lista de comportamientos vacía si la API responde con una lista vacía', async () => {
    vi.mocked(sessionModule.read_session).mockReturnValue({
        access_token: 'fake-token',
    });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue([]);
    render(<BehaviorPage/>);
    expect(await screen.findByText('Comportamientos')).toBeInTheDocument();
    expect(screen.queryByText('Comportamiento 1')).not.toBeInTheDocument();
  });

  it('Debe mostrar un mensaje de error si la API devuelve un error 401', async () => {
    vi.mocked(sessionModule.read_session).mockReturnValue({
        access_token: 'fake-token',
    });
    vi.mocked(apiModule.get_behaviors).mockRejectedValue(new Error('401'));
    render(<BehaviorPage />);
    expect(apiModule.get_behaviors).toHaveBeenCalledTimes(1);

    expect(await screen.findByText(/Error al obtener los comportamientos/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reintentar/i })).toBeInTheDocument();
    expect(screen.queryByText(/CARGANDO TÁCTICAS/i)).not.toBeInTheDocument(); // ya no está cargando
  });

  it ('El boton "Reintentar" recarga la página', async () => {
    vi.mocked(sessionModule.read_session).mockReturnValue({
        access_token: 'fake-token',
    });
    vi.mocked(apiModule.get_behaviors).mockRejectedValue(new Error('500'));
    render(<BehaviorPage />);
    expect(await screen.findByText(/Error al obtener los comportamientos/i)).toBeInTheDocument();
    const retryButton = screen.getByRole('button', { name: /Reintentar/i });
    const user = userEvent.setup();
    await user.click(retryButton);
    
  });

  it('Debe volver al menú al presionar el botón', async () => {
    const user = userEvent.setup()
    vi.mocked(sessionModule.read_session).mockReturnValue({
      access_token: 'fake-token',
    })
    vi.mocked(apiModule.get_behaviors).mockResolvedValue([])
    render(<BehaviorPage />)
    await user.click(screen.getByRole('button', { name: /volver al menú/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/home')
  })
  
  it('Debe abrir el modal con el código y el nombre al hacer clic en "Ver detalles"', async () => {
    const mockBehaviors = [
      { id: 'b1', name: 'Presión Alta', code: 'def behavior(player):\n  player.correr()', isDefault: true },
    ];
    vi.mocked(sessionModule.read_session).mockReturnValue({ access_token: 'fake-token' });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue(mockBehaviors);

    render(<BehaviorPage />);
    
    expect(await screen.findByText('Presión Alta')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /ver detalles/i }));

    const modal = screen.getByRole('dialog');
    expect(modal).toBeInTheDocument();
    expect(within(modal).getByText(/def behavior\(player\):/)).toBeInTheDocument();
    expect(within(modal).getByRole('button', { name: /cerrar/i })).toBeInTheDocument();
  });

  it('Debe cerrar el modal al hacer clic en el botón correspondiente', async () => {
    const mockBehaviors = [
      { id: 'b1', name: 'Presión Alta', code: 'def behavior(player):\n  player.correr()', isDefault: true },
    ];
    vi.mocked(sessionModule.read_session).mockReturnValue({ access_token: 'fake-token' });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue(mockBehaviors);

    render(<BehaviorPage />);
    expect(await screen.findByText('Presión Alta')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /ver detalles/i }));
    
    const btnCerrar = screen.getByRole('button', { name: /cerrar/i });
    await user.click(btnCerrar);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Debe abrir el modal con los datos exactos del comportamiento clickeado sin mezclar datos', async () => {
    const mockBehaviors = [
      { id: 'b1', name: 'Defensa Férrea', code: 'def defender():\n  pass', isDefault: true },
      { id: 'b2', name: 'Ataque Rápido', code: 'def atacar():\n  pass', isDefault: false },
    ];
    vi.mocked(sessionModule.read_session).mockReturnValue({ access_token: 'fake-token' });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue(mockBehaviors);

    render(<BehaviorPage />);
    
    expect(await screen.findByText('Defensa Férrea')).toBeInTheDocument();
    expect(screen.getByText('Ataque Rápido')).toBeInTheDocument();

    const user = userEvent.setup();
    const botonesDetalles = screen.getAllByRole('button', { name: /ver detalles/i });
    
    await user.click(botonesDetalles[1]);

    const modal = screen.getByRole('dialog');
    expect(modal).toBeInTheDocument();
    expect(within(modal).getByText(/def atacar\(\):/)).toBeInTheDocument();
    expect(within(modal).queryByText(/def defender\(\):/)).not.toBeInTheDocument();
  });

  it('Debe mostrar "Sin código" cuando el comportamiento no tiene código', async () => {
    const mockBehaviors = [
      { id: 'b1', name: 'Comportamiento sin código', code: '', isDefault: false },
    ];
    vi.mocked(sessionModule.read_session).mockReturnValue({ access_token: 'fake-token' });
    vi.mocked(apiModule.get_behaviors).mockResolvedValue(mockBehaviors);

    render(<BehaviorPage />);
    
    expect(await screen.findByText('Comportamiento sin código')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /ver detalles/i }));

    const modal = screen.getByRole('dialog');
    expect(within(modal).getByText('Sin código')).toBeInTheDocument();
  });
})