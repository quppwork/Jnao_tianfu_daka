import { describe, it, expect } from "vitest";
import { getHint } from "../src/data/questionHints";

describe("getHint", () => {
  it("returns a non-empty string for Q1 (思者)", () => {
    const hint = getHint(1);
    expect(hint).toBeTruthy();
    expect(hint).toContain("思者");
  });

  it("returns a non-empty string for Q35 (行者/赢者)", () => {
    const hint = getHint(35);
    expect(hint).toBeTruthy();
  });

  it("returns hint for last question (Q105)", () => {
    const hint = getHint(105);
    expect(hint).toBeTruthy();
    expect(hint.length).toBeGreaterThan(0);
  });

  it("returns empty string for a non-existent question", () => {
    expect(getHint(999)).toBe("");
    expect(getHint(0)).toBe("");
    expect(getHint(-1)).toBe("");
  });

  it("all 105 hints are non-empty", () => {
    for (let i = 1; i <= 105; i++) {
      const hint = getHint(i);
      expect(hint, `Q${i} hint should not be empty`).toBeTruthy();
    }
  });
});
