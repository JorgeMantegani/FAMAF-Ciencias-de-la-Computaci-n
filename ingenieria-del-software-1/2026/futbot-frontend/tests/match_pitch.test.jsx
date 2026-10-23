import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import MatchPitch from '../src/components/match_pitch'

afterEach(cleanup)

it('ubica el centro y ambos equipos y excluye a los suplentes', () => {
  const { container } = render(<MatchPitch state={{
    home_club: { club_id: 'home', name: 'Local' },
    away_club: { club_id: 'away', name: 'Visitante' },
    ball: { x: 0, y: 0 },
    players: [
      { player_id: 'h', club_id: 'home', name: 'Ana', on_field: true, position: { x: -25, y: 15 } },
      { player_id: 'a', club_id: 'away', name: 'Luis', on_field: true, position: { x: 25, y: -15 } },
      { player_id: 's', club_id: 'home', name: 'Suplente', on_field: false, position: { x: 0, y: 0 } },
      { player_id: 'n', club_id: 'away', name: 'Sin posición', on_field: true, position: null },
    ],
  }} />)
  expect(container.querySelectorAll('.match-pitch-player')).toHaveLength(2)
  expect(container.querySelector('.match-pitch-player--home')).toHaveAttribute('transform', 'translate(358 172.5)')
  expect(container.querySelector('.match-pitch-player--away')).toHaveAttribute('transform', 'translate(938 449.5)')
  expect(container.querySelector('.match-pitch-ball')).toHaveAttribute('transform', 'translate(648 311)')
})
