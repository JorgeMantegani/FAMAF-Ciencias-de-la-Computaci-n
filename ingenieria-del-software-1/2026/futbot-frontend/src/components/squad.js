const SLOTS_PER_ROLE = 3

const empty_slot = () => ({ playerId: '', behaviorId: '' })

export function empty_squad() {
  return {
    starters: Array.from({ length: SLOTS_PER_ROLE }, empty_slot),
    substitutes: Array.from({ length: SLOTS_PER_ROLE }, empty_slot),
  }
}

const is_filled = (value) => value !== '' && value != null

export function is_squad_complete(squad) {
  const slots = [...squad.starters, ...squad.substitutes]

  return (
    slots.length === SLOTS_PER_ROLE * 2 &&
    slots.every((slot) => is_filled(slot.playerId) && is_filled(slot.behaviorId)) &&
    new Set(slots.map((slot) => String(slot.playerId))).size === slots.length
  )
}
