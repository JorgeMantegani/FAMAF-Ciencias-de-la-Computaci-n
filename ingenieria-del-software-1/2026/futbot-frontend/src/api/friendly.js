// src/api/friendly.js
import { request } from './client'

export async function createFriendlyRoom(squadData) {
  return request('/api/friendly/rooms', {
    method: 'POST',
    body: JSON.stringify(squadData),
  });
}

// Datos de prueba para desarrollo local cuando el backend da 404
const MOCK_PLAYERS = [
  { id: '1', name: 'Delantero Rayo' },
  { id: '2', name: 'Mediocampista Muro' },
  { id: '3', name: 'Defensor Roca' },
  { id: '4', name: 'Arquero Pulpo' },
  { id: '5', name: 'Extremo Veloz' },
  { id: '6', name: 'Pivote Estático' },
];

const MOCK_BEHAVIORS = [
  { id: '1', name: 'Ataque Agresivo', is_preprogrammed: true },
  { id: '2', name: 'Defensa Bajas', is_preprogrammed: true },
  { id: '3', name: 'Contraataque Rápido', is_preprogrammed: false },
  { id: '4', name: 'Posesión y Pase', is_preprogrammed: false },
];

export async function getMyPlayers() {
  try {
    return await request('/api/players');
  } catch (error) {
    if (error.status === 404) {
      console.warn('Endpoint /api/players/me dio 404. Usando datos mock de jugadores.');
      return MOCK_PLAYERS;
    }
    throw error;
  }
}

export async function getMyBehaviors() {
  try {
    return await request('/api/behaviors');
  } catch (error) {
    if (error.status === 404) {
      console.warn('Endpoint /api/behaviors/me dio 404. Usando datos mock de comportamientos.');
      return MOCK_BEHAVIORS;
    }
    throw error;
  }
}