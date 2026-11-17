export function parse_change_result(raw) {
  let message
  try {
    message = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return null
  }
  if (message?.event === 'BEHAVIOR_CHANGED') {
    const playerId = message.payload?.playerId ?? message.playerId
    return playerId == null ? { ok: true } : { ok: true, playerId }
  }

  if (
    message?.type === 'error' &&
    typeof message.error_code === 'string' &&
    message.error_code.startsWith('BEHAVIOR_CHANGE_')
  ) {
    const playerId = message.payload?.playerId ?? message.playerId
    return {
      ok: false,
      message: message.message || 'No se pudo cambiar el comportamiento',
      ...(playerId == null ? {} : { playerId }),
    }
  }
  return null
}