import { describe, it, expect } from "vitest";
import { build_change_behavior_message } from "../src/match/change_behavior_message";

describe("build_change_behavior_message", () => {
  it("arma el mensaje CHANGE_BEHAVIOR del contrato", () => {
    expect(build_change_behavior_message("p1", "b2")).toEqual({
      action: "CHANGE_BEHAVIOR",
      payload: { playerId: "p1", behaviorId: "b2" },
    });
  });

  it("no convierte el tipo de los ids", () => {
    const msg = build_change_behavior_message("p1", "b2");
    expect(typeof msg.payload.playerId).toBe("string");
  });

  it("tira error si falta playerId", () => {
    expect(() => build_change_behavior_message(undefined, "b2")).toThrow();
  });

  it("tira error si falta behaviorId", () => {
    expect(() => build_change_behavior_message("p1", undefined)).toThrow();
  });
});