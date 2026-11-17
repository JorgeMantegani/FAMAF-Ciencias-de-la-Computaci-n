export function build_change_behavior_message(playerId, behaviorId) {
  if (!playerId || !behaviorId) {
    throw new Error("playerId y behaviorId son obligatorios");
  }
  return {
    action: "CHANGE_BEHAVIOR",
    payload: { playerId, behaviorId },
  };
}