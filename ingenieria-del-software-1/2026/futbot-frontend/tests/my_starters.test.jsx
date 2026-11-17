import { describe, it, expect } from 'vitest'
import { get_my_starters } from '../src/match/my_starters'

const state = {
  players: [
    { player_id: 'p1', club_id: 'home', name: 'Ana', behavior_id: 'b1', on_field: true },
    { player_id: 'p2', club_id: 'home', name: 'Beto', behavior_id: 'b1', on_field: false },
    { player_id: 'p3', club_id: 'away', name: 'Caro', behavior_id: 'b2', on_field: true },
  ],
}

describe('get_my_starters', () => {
  it('devuelve solo los jugadores en cancha de mi club', () => {
    expect(get_my_starters(state, 'home')).toEqual([{ id: 'p1', name: 'Ana', behavior_id: 'b1' }])
  })

  it('devuelve lista vacía si mi club no tiene jugadores en cancha', () => {
    expect(get_my_starters(state, 'otro')).toEqual([])
  })
})