import { describe, it, expect } from "vitest";
import { randomAck, milestoneFor } from "../src/lib/quizFeedback";

describe("randomAck", () => {
  it("returns a non-empty string", () => {
    const ack = randomAck();
    expect(ack).toBeTruthy();
    expect(typeof ack).toBe("string");
    expect(ack.length).toBeGreaterThan(0);
  });

  it("returns different values across multiple calls (statistical)", () => {
    const results = new Set<string>();
    for (let i = 0; i < 50; i++) {
      results.add(randomAck());
    }
    // With 8 fallback phrases, 50 calls should produce at least 2 distinct values
    expect(results.size).toBeGreaterThanOrEqual(2);
  });
});

describe("milestoneFor", () => {
  it("returns milestone message at Q5", () => {
    expect(milestoneFor(5)).toBeTruthy();
    expect(milestoneFor(5)).toContain("五题");
  });

  it("returns milestone message at Q15", () => {
    expect(milestoneFor(15)).toBeTruthy();
    expect(milestoneFor(15)).toContain("半");
  });

  it("returns milestone message at Q25", () => {
    expect(milestoneFor(25)).toBeTruthy();
    expect(milestoneFor(25)).toContain("三分之一");
  });

  it("returns milestone message at Q35", () => {
    expect(milestoneFor(35)).toBeTruthy();
    expect(milestoneFor(35)).toContain("完成");
  });

  it("returns undefined for non-milestone question numbers", () => {
    expect(milestoneFor(1)).toBeUndefined();
    expect(milestoneFor(3)).toBeUndefined();
    expect(milestoneFor(7)).toBeUndefined();
    expect(milestoneFor(14)).toBeUndefined();
    expect(milestoneFor(26)).toBeUndefined();
  });

  it("returns undefined for out-of-range numbers", () => {
    expect(milestoneFor(0)).toBeUndefined();
    expect(milestoneFor(36)).toBeUndefined();
    expect(milestoneFor(100)).toBeUndefined();
  });
});
