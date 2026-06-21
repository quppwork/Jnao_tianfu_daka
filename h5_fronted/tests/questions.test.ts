import { describe, it, expect } from "vitest";
import { getQuestionsBySet, getQuestionById } from "../src/data/questions";

describe("getQuestionsBySet", () => {
  it("returns 35 adult questions", () => {
    const questions = getQuestionsBySet("adult");
    expect(questions).toHaveLength(35);
    questions.forEach((q) => {
      expect(q.id).toBeGreaterThanOrEqual(1);
      expect(q.id).toBeLessThanOrEqual(35);
      expect(q.set).toBe("adult");
      expect(q.text).toBeTruthy();
    });
  });

  it("returns 35 child questions", () => {
    const questions = getQuestionsBySet("child");
    expect(questions).toHaveLength(35);
    questions.forEach((q) => {
      expect(q.id).toBeGreaterThanOrEqual(36);
      expect(q.id).toBeLessThanOrEqual(70);
      expect(q.set).toBe("child");
      expect(q.text).toBeTruthy();
    });
  });

  it("returns 35 child_backup questions", () => {
    const questions = getQuestionsBySet("child_backup");
    expect(questions).toHaveLength(35);
    questions.forEach((q) => {
      expect(q.id).toBeGreaterThanOrEqual(71);
      expect(q.id).toBeLessThanOrEqual(105);
      expect(q.set).toBe("child_backup");
      expect(q.text).toBeTruthy();
    });
  });

  it("returns empty array for unknown set", () => {
    expect(getQuestionsBySet("unknown")).toEqual([]);
  });

  it("all three sets have no overlapping IDs", () => {
    const adult = getQuestionsBySet("adult").map((q) => q.id);
    const child = getQuestionsBySet("child").map((q) => q.id);
    const backup = getQuestionsBySet("child_backup").map((q) => q.id);
    const all = [...adult, ...child, ...backup];
    expect(new Set(all).size).toBe(105);
  });
});

describe("getQuestionById", () => {
  it("returns question for valid ID 1", () => {
    const q = getQuestionById(1);
    expect(q).toBeDefined();
    expect(q!.id).toBe(1);
    expect(q!.set).toBe("adult");
  });

  it("returns question for child question (ID 36)", () => {
    const q = getQuestionById(36);
    expect(q).toBeDefined();
    expect(q!.id).toBe(36);
    expect(q!.set).toBe("child");
  });

  it("returns question for backup question (ID 71)", () => {
    const q = getQuestionById(71);
    expect(q).toBeDefined();
    expect(q!.id).toBe(71);
    expect(q!.set).toBe("child_backup");
  });

  it("returns question for last question (ID 105)", () => {
    const q = getQuestionById(105);
    expect(q).toBeDefined();
    expect(q!.id).toBe(105);
  });

  it("returns undefined for invalid ID", () => {
    expect(getQuestionById(0)).toBeUndefined();
    expect(getQuestionById(106)).toBeUndefined();
    expect(getQuestionById(999)).toBeUndefined();
  });
});
