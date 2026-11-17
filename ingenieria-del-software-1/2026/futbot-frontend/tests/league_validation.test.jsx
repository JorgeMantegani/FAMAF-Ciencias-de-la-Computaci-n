import { describe, it, expect } from "vitest";
import { validate_league } from "../src/components/league_validation";

// Genera una lista de jugadores con playerId y behaviorId unicos
function createPlayers(count, startId = 1) {
  return Array.from({ length: count }, (_, i) => ({
    playerId: String(startId + i),
    behaviorId: String(startId + i + 100),
  }));
}

const valid_input = {
  name: "Liga de prueba",
  is_private: false,
  min_clubs: 3,
  max_clubs: 30,
  match_duration: 90,
  starters: createPlayers(3, 1),
  substitutes: createPlayers(3, 4),
};

const errorsWith = (changes) => validate_league({ ...valid_input, ...changes });

describe("validate_league", () => {
  it("acepta una liga válida", () => {
    expect(validate_league(valid_input)).toEqual({});
  });

  // Name vacio
  it("rechaza un nombre con solo espacios", () => {
    expect(errorsWith({ name: "   " }).name).toBeDefined();
  });

  // Test minimo de clubes
  describe("min_clubs", () => {
    it("acepta 3", () => {
      expect(errorsWith({ min_clubs: 3 }).min_clubs).toBeUndefined();
    });
    it("rechaza un valor no numérico", () => {
      expect(errorsWith({ min_clubs: "abc" }).min_clubs).toBeDefined();
    });
    it("rechaza un numero no entero", () => {
      expect(errorsWith({ min_clubs: 2.5 }).min_clubs).toBeDefined();
    });
    it("rechaza 2", () => {
      expect(errorsWith({ min_clubs: 2 }).min_clubs).toBeDefined();
    });
  });

  // Test maximo de clubes
  describe("max_clubs", () => {
    it("acepta 30", () => {
      expect(errorsWith({ max_clubs: 30 }).max_clubs).toBeUndefined();
    });
    it("acepta max igual a min", () => {
      expect(
        errorsWith({ min_clubs: 10, max_clubs: 10 }).max_clubs
      ).toBeUndefined();
    });
    it("rechaza 31", () => {
      expect(errorsWith({ max_clubs: 31 }).max_clubs).toBeDefined();
    });
    it("rechaza max menor que min", () => {
      expect(
        errorsWith({ min_clubs: 10, max_clubs: 9 }).max_clubs
      ).toBeDefined();
    });
  });

  // Test match duration
  describe("match_duration", () => {
    it("acepta 90", () => {
      expect(errorsWith({ match_duration: 90 }).match_duration).toBeUndefined();
    });
    it("rechaza un valor no numérico", () => {
      expect(errorsWith({ match_duration: "abc" }).match_duration).toBeDefined();
    });
    it("rechaza un numero no entero", () => {
      expect(errorsWith({ match_duration: 45.5 }).match_duration).toBeDefined();
    });
    it("rechaza 0", () => {
      expect(errorsWith({ match_duration: 0 }).match_duration).toBeDefined();
    });
  });

  // Test squad
  describe("plantel", () => {
    it("rechaza 2 titulares", () => {
      expect(errorsWith({ starters: createPlayers(2, 1) }).starters).toBeDefined();
    });
    it("rechaza 2 suplentes", () => {
      expect(
        errorsWith({ substitutes: createPlayers(2, 4) }).substitutes
      ).toBeDefined();
    });
  });

  describe("jugadores", () => {
    it("rechaza un jugador repetido entre titulares y suplentes", () => {
      const substitutes = [{ ...valid_input.starters[0] }, ...createPlayers(2, 5)];
      expect(errorsWith({ substitutes }).duplicatePlayers).toBeDefined();
    });
    it("rechaza un jugador sin behaviorId", () => {
      const starters = [{ playerId: "1" }, ...createPlayers(2, 2)];
      expect(errorsWith({ starters }).behaviorIds).toBeDefined();
    });
    it("rechaza un jugador sin playerId", () => {
      const starters = [{ behaviorId: "101" }, ...createPlayers(2, 2)];
      expect(errorsWith({ starters }).playerIds).toBeDefined();
    });
  });

  // Test password
  describe("password", () => {
    it("rechaza sin contraseña", () => {
      expect(
        errorsWith({ is_private: true, password: "" }).password
      ).toBeDefined();
    });

    it("rechaza contraseña con 5 caracteres", () => {
      expect(
        errorsWith({ is_private: true, password: "abcde" }).password
      ).toBeDefined();
    });

    it("rechaza una contraseña con espacios", () => {
      expect(
        errorsWith({ is_private: true, password: "abc 12" }).password
      ).toBeDefined();
    });

    it("acepta una contraseña con 6 caracteres sin espacios", () => {
      expect(
        errorsWith({ is_private: true, password: "abc123" }).password
      ).toBeUndefined();
    });

    it("acepta una pública sin contraseña", () => {
      expect(
        errorsWith({ is_private: false, password: "" }).password
      ).toBeUndefined();
    });
    it("rechaza una privada sin password definido", () => {
      expect(
        errorsWith({ is_private: true, password: undefined }).password
      ).toBeDefined();
    });
    it("acepta una contraseña de exactamente 72 bytes", () => {
      expect(
        errorsWith({ is_private: true, password: "a".repeat(72) }).password
      ).toBeUndefined();
    });

    it("rechaza una contraseña de 73 bytes", () => {
      expect(
        errorsWith({ is_private: true, password: "a".repeat(73) }).password
      ).toBeDefined();
    });

    it("rechaza una contraseña con 37 caracteres que ocupan 74 bytes", () => {
      // "ñ" ocupa 2 bytes en UTF-8: 37 caracteres = 74 bytes
      expect(
        errorsWith({ is_private: true, password: "ñ".repeat(37) }).password
      ).toBeDefined();
    });

    it("acepta una contraseña con 36 caracteres que ocupan 72 bytes", () => {
      expect(
        errorsWith({ is_private: true, password: "ñ".repeat(36) }).password
      ).toBeUndefined();
    });

  });

});