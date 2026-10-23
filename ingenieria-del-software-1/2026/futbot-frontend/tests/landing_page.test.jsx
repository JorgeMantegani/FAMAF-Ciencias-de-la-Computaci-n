import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import LandingPage from '../src/pages/landing_page';

// Same shape the login flow stores (see src/auth/session.js).
const store_session = (expires_at) => {
  localStorage.setItem('futbot.session', JSON.stringify({
    access_token: 'access-token',
    refresh_token: 'refresh-token',
    club_id: 'club-1',
    expires_at,
  }));
};

const now_in_seconds = () => Math.floor(Date.now() / 1000);

// Real routes with markers, so the tests check the actual navigation.
const renderLanding = () => {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<p>Pantalla de login</p>} />
        <Route path="/register" element={<p>Pantalla de registro</p>} />
        <Route path="/home" element={<p>Pantalla de home</p>} />
      </Routes>
    </MemoryRouter>
  );
};

describe('LandingPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('Debe renderizar los textos principales y ambos botones', () => {
    renderLanding();

    expect(screen.getByText(/El club táctico de FutBot/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: /Toma el mando\. El partido empieza aquí\./i })).toBeInTheDocument();
    expect(screen.getByText(/Prepara formaciones, programa cada movimiento/i)).toBeInTheDocument();
    expect(screen.getByText(/Elige cómo entrar al terreno de juego/i)).toBeInTheDocument();
    expect(screen.getByText(/¿Ya tienes club\? Retoma tu estrategia\./i)).toBeInTheDocument();
    expect(screen.getByText(/¿Nuevo fichaje\? Crea tu vestuario\./i)).toBeInTheDocument();
    expect(screen.getByText(/Conexión cifrada · Datos protegidos/i)).toBeInTheDocument();
    expect(screen.getByText(/Temporada 04 \/ 2026/i)).toBeInTheDocument();

    expect(screen.getByRole('link', { name: /Iniciar sesión/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Crear cuenta/i })).toBeInTheDocument();
  });

  it('Debe renderizar el tablero táctico con jugadores y métricas', () => {
    renderLanding();

    expect(screen.getByTestId('tactical-board')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Diseña la próxima jugada\./i })).toBeInTheDocument();
    ['8', '9', '10', '1'].forEach((number) => {
      expect(screen.getByText(number, { exact: true })).toBeInTheDocument();
    });
    expect(screen.getByText('4-3-3')).toBeInTheDocument();
    expect(screen.getByText('ALTA')).toBeInTheDocument();
    expect(screen.getByText('+12%')).toBeInTheDocument();
  });

  it('Debe navegar a /login al presionar "Iniciar sesión"', async () => {
    const user = userEvent.setup();
    renderLanding();

    await user.click(screen.getByRole('link', { name: /Iniciar sesión/i }));

    expect(screen.getByText('Pantalla de login')).toBeInTheDocument();
  });

  it('Debe navegar a /register al presionar "Crear cuenta"', async () => {
    const user = userEvent.setup();
    renderLanding();

    await user.click(screen.getByRole('link', { name: /Crear cuenta/i }));

    expect(screen.getByText('Pantalla de registro')).toBeInTheDocument();
  });

  it('Debe redirigir a /home si hay una sesión con token vigente', () => {
    store_session(now_in_seconds() + 3600);
    renderLanding();

    expect(screen.getByText('Pantalla de home')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Iniciar sesión/i })).not.toBeInTheDocument();
  });

  it('Debe mostrar la landing si el token está vencido', () => {
    store_session(now_in_seconds() - 60);
    renderLanding();

    expect(screen.getByRole('link', { name: /Iniciar sesión/i })).toBeInTheDocument();
  });

  it('Debe mostrar la landing si la sesión guardada está corrupta', () => {
    localStorage.setItem('futbot.session', 'no-es-json');
    renderLanding();

    expect(screen.getByRole('link', { name: /Iniciar sesión/i })).toBeInTheDocument();
  });
});
