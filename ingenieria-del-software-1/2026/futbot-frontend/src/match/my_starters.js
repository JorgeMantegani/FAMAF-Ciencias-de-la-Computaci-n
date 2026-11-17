export function get_my_starters(state, club_id) {
  return state.players
    .filter((p) => p.club_id === club_id && p.on_field)
    .map((p) => ({ id: p.player_id, name: p.name, behavior_id: p.behavior_id }))
}