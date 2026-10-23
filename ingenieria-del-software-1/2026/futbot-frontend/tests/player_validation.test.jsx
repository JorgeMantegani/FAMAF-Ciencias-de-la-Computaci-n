import { describe, expect, it } from 'vitest';
import { validate_player } from '../src/components/player_validation.jsx';

// Jugador valido de base
const base = {
  name: 'Messi',
  power: '60',
  agility: '60',
  control: '60',
  speed: '60',
  strength: '60',
};

// Tests para la funcion validate_player
describe('validate_player', () => {
  describe('caso valido', () => {
    it('acepta un jugador valido cuyos atributos suman 300', () => {
      const result = validate_player(base);
      expect(result.errors).toEqual({});
      expect(result.sum).toBe(300);
    });

    it('acepta los valores limite 20 y 100', () => {
      const result = validate_player({
        ...base,
        power: '100',
        agility: '100',
        control: '20',
        speed: '40',
        strength: '40',
      });
      expect(result.errors).toEqual({});
      expect(result.sum).toBe(300);
    });

    it('acepta un nombre de exactamente 3 caracteres', () => {
      const result = validate_player({ ...base, name: 'Leo' });
      expect(result.errors.name).toBeUndefined();
    });
  });

  // Tests para el nombre
  describe('nombre', () => {
    it('rechaza un nombre vacio', () => {
      const result = validate_player({ ...base, name: '' });
      expect(result.errors.name).toBeDefined();
    });

    it('rechaza un nombre de solo espacios', () => {
      const result = validate_player({ ...base, name: '     ' });
      expect(result.errors.name).toBeDefined();
    });

    it('rechaza un nombre de menos de 3 caracteres', () => {
      const result = validate_player({ ...base, name: 'Jo' });
      expect(result.errors.name).toBeDefined();
    });

    it('ignora los espacios alrededor al contar caracteres', () => {
      const result = validate_player({ ...base, name: ' Jo ' });
      expect(result.errors.name).toBeDefined();
    });
  });

  // Tests para los atributos
  describe('atributos', () => {
    it.each([
      ['vacio', ''],
      ['solo espacios', '   '],
      ['letras', 'abc'],
      ['decimal', '20.5'],
      ['notación cientifica', '1e2'],
      ['negativo', '-30'],
      ['con espacios', ' 60 '],
    ])('rechaza un atributo %s', (_caso, valor) => {
      const result = validate_player({ ...base, power: valor });
      expect(result.errors.power).toBeDefined();
    });

    it('rechaza un atributo menor a 20', () => {
      const result = validate_player({ ...base, speed: '19' });
      expect(result.errors.speed).toBeDefined();
    });

    it('rechaza un atributo mayor a 100', () => {
      const result = validate_player({ ...base, strength: '101' });
      expect(result.errors.strength).toBeDefined();
    });

    it('marca error solo en el atributo invalido', () => {
      const result = validate_player({ ...base, control: '19' });
      expect(Object.keys(result.errors)).toEqual(['control']);
    });
  });

  // Tests para la suma de atributos
  describe('suma', () => {
    it('rechaza una suma de 299', () => {
      const result = validate_player({ ...base, power: '59' });
      expect(result.errors.sum).toBeDefined();
      expect(result.sum).toBe(299);
    });

    it('rechaza una suma de 301', () => {
      const result = validate_player({ ...base, power: '61' });
      expect(result.errors.sum).toBeDefined();
      expect(result.sum).toBe(301);
    });

    it('no informa error de suma si hay un atributo invalido', () => {
      const result = validate_player({ ...base, power: 'abc' });
      expect(result.errors.sum).toBeUndefined();
      expect(result.sum).toBeNull();
    });

    it('no informa error de suma si falta un atributo', () => {
      const result = validate_player({ ...base, agility: '' });
      expect(result.errors.sum).toBeUndefined();
      expect(result.sum).toBeNull();
    });
  });
});