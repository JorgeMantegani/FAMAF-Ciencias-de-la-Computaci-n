import { describe, it, expect } from 'vitest'
import { parse_change_result } from '../src/match/change_behavior_result'

describe('parse_change_result', () => {
  it('devuelve el mensaje del servidor en un error del cambio', () => {
    const raw = JSON.stringify({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE', message: 'Comportamiento no disponible' })
    expect(parse_change_result(raw)).toEqual({ ok: false, message: 'Comportamiento no disponible' })
  })

  it('usa un mensaje por defecto si el error no trae texto', () => {
    const raw = JSON.stringify({ type: 'error', ok: false, error_code: 'BEHAVIOR_CHANGE_INVALID_PLAYER' })
    expect(parse_change_result(raw).message).toBe('No se pudo cambiar el comportamiento')
  })

  it('ignora errores que no son del cambio de comportamiento', () => {
    const raw = JSON.stringify({ type: 'error', status: 404, message: 'El partido no existe.' })
    expect(parse_change_result(raw)).toBeNull()
  })

  it('devuelve null con otros mensajes o JSON inválido', () => {
    expect(parse_change_result(JSON.stringify({ event: 'GOAL_SCORED' }))).toBeNull()
    expect(parse_change_result('no es json')).toBeNull()
  })
})