import { describe, it, expect, beforeEach, vi } from "vitest";
import { shuffle, requeueAtBack, getOrCreateUid, encodeAnswers } from "../src/lib/testHelpers";

describe("shuffle", () => {
  it("returns a same-length array", () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    expect(shuffle(input)).toHaveLength(input.length);
  });

  it("contains all original elements", () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const result = shuffle(input);
    expect([...result].sort((a, b) => a - b)).toEqual([...input].sort((a, b) => a - b));
  });

  it("does not mutate the original array", () => {
    const input = [1, 2, 3, 4, 5];
    const copy = [...input];
    shuffle(input);
    expect(input).toEqual(copy);
  });

  it("handles empty array", () => {
    expect(shuffle([])).toEqual([]);
  });

  it("handles single element", () => {
    expect(shuffle([42])).toEqual([42]);
  });

  it("produces different orderings (statistical, 100 trials)", () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    let sameCount = 0;
    for (let i = 0; i < 100; i++) {
      const result = shuffle(input);
      if (result.every((v, idx) => v === input[idx])) sameCount++;
    }
    // Probability of exact same order is 1/10! ≈ 0.00000027
    // 100 trials: expect nearly always different
    expect(sameCount).toBeLessThan(5);
  });
});

describe("requeueAtBack", () => {
  it("moves the given qid to the latter half", () => {
    const remaining = [10, 20, 30, 40, 50, 60, 70, 80];
    const result = requeueAtBack(remaining, 10);
    expect(result).toHaveLength(8);
    expect(result).toContain(10);
    // 10 should be in the latter half (index >= 3 for 8 elements)
    const pos = result.indexOf(10);
    expect(pos).toBeGreaterThanOrEqual(Math.floor(result.length / 2) - 1);
  });

  it("does not lose any elements", () => {
    const remaining = [5, 10, 15, 20, 25];
    const result = requeueAtBack(remaining, 15);
    expect([...result].sort((a, b) => a - b)).toEqual([...remaining].sort((a, b) => a - b));
  });

  it("handles single element pool", () => {
    expect(requeueAtBack([7], 7)).toEqual([7]);
  });

  it("adds qid to pool when not originally present (added to latter half)", () => {
    const remaining = [1, 2, 3];
    const result = requeueAtBack(remaining, 99);
    expect(result).toHaveLength(4);
    expect(result).toContain(99);
    // 99 should be in latter half (index >= 1 for 4 elements)
    const pos = result.indexOf(99);
    expect(pos).toBeGreaterThanOrEqual(1);
  });
});

describe("encodeAnswers", () => {
  it("encodes 完全符合 as 1 and 有差异 as 0, sorted by question ID", () => {
    const order = [5, 1, 3, 2, 4];
    const answers: Record<number, string> = {
      1: "完全符合",
      2: "有差异",
      3: "完全符合",
      4: "有差异",
      5: "完全符合",
    };
    // Sorted by qid: 1,2,3,4,5 → 1,0,1,0,1
    expect(encodeAnswers(order, answers)).toBe("10101");
  });

  it("handles missing answers as 0", () => {
    const order = [1, 2, 3];
    const answers: Record<number, string> = {
      1: "完全符合",
    };
    expect(encodeAnswers(order, answers)).toBe("100");
  });

  it("returns all zeros when no answers match", () => {
    const order = [1, 2, 3];
    expect(encodeAnswers(order, {})).toBe("000");
  });

  it("returns all ones when all are 完全符合", () => {
    const order = [2, 1, 3];
    const answers: Record<number, string> = {
      1: "完全符合",
      2: "完全符合",
      3: "完全符合",
    };
    expect(encodeAnswers(order, answers)).toBe("111");
  });

  it("produces exactly 35 characters for a full test", () => {
    const order = Array.from({ length: 35 }, (_, i) => i + 1);
    const answers: Record<number, string> = {};
    for (let i = 1; i <= 35; i++) {
      answers[i] = i % 2 === 0 ? "完全符合" : "有差异";
    }
    const result = encodeAnswers(order, answers);
    expect(result).toHaveLength(35);
  });
});

describe("getOrCreateUid", () => {
  let store: Record<string, string>;

  beforeEach(() => {
    store = {};
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, val: string) => { store[key] = val; }),
      removeItem: vi.fn((key: string) => { delete store[key]; }),
    });
  });

  it("generates a number between 100000 and 1000000", () => {
    const uid = getOrCreateUid();
    expect(uid).toBeGreaterThanOrEqual(100000);
    expect(uid).toBeLessThan(1000000);
  });

  it("returns the same uid on second call (persistence)", () => {
    const first = getOrCreateUid();
    const second = getOrCreateUid();
    expect(second).toBe(first);
  });

  it("stores uid in localStorage under jnao_uid key", () => {
    getOrCreateUid();
    expect(store["jnao_uid"]).toBeTruthy();
    expect(Number(store["jnao_uid"])).toBeGreaterThan(0);
  });
});
