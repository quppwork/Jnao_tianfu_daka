import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressBar } from "../src/components/ProgressBar";

describe("ProgressBar", () => {
  it("shows current/total and percentage", () => {
    render(<ProgressBar current={3} total={35} />);
    expect(screen.getByText("3/35")).toBeInTheDocument();
    expect(screen.getByText("9%")).toBeInTheDocument();
  });

  it("shows 0% at start", () => {
    render(<ProgressBar current={0} total={35} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("shows 100% when complete", () => {
    render(<ProgressBar current={35} total={35} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("rounds percentage correctly", () => {
    render(<ProgressBar current={1} total={3} />);
    expect(screen.getByText("33%")).toBeInTheDocument();
  });

  it("renders progress bar fill with correct width", () => {
    const { container } = render(<ProgressBar current={7} total={35} />);
    const fill = container.querySelector('[style*="width"]');
    expect(fill).toBeTruthy();
    expect(fill?.getAttribute("style")).toContain("width: 20%");
  });
});
