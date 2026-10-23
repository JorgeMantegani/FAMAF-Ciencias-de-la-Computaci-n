import { request } from './client';
import { read_session } from '../auth/session';

// Se encarga de crear un jugador en el backend.
export async function createPlayer({ name, power, agility, control, speed, strength }) {
  const session = read_session();

  if (!session) {
    throw new Error('Tu sesión venció. Iniciá sesión de nuevo.');
  }

  return request('/api/players', {
    method: 'POST',
    headers: { Authorization: `Bearer ${session.access_token}` },
    body: JSON.stringify({
      name: name.trim(),
      power: Number(power),
      agility: Number(agility),
      control: Number(control),
      speed: Number(speed),
      strength: Number(strength),
    }),
  });
}
