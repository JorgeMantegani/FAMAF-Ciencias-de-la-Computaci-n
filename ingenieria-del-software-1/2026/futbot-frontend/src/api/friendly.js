// src/api/friendly.js
import { request, list_players, list_behaviors } from './client';

export async function createFriendlyRoom(squadData) {
  return request('/api/friendly/rooms', {
    method: 'POST',
    body: JSON.stringify(squadData),
  });
}

export function getMyPlayers() {
  return list_players();
}

export function getMyBehaviors() {
  return list_behaviors();
}