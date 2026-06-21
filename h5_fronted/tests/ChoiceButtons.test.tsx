import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChoiceButtons } from "../src/components/ChoiceButtons";

describe("ChoiceButtons", () => {
  const choices = ["完全符合", "有差异"];

  it("renders all choice buttons", () => {
    render(<ChoiceButtons choices={choices} onSelect={() => {}} />);
    expect(screen.getByText("完全符合")).toBeInTheDocument();
    expect(screen.getByText("有差异")).toBeInTheDocument();
  });

  it("fires onSelect with the chosen text", () => {
    const onSelect = vi.fn();
    render(<ChoiceButtons choices={choices} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("完全符合"));
    expect(onSelect).toHaveBeenCalledWith("完全符合");
  });

  it("fires onSelect with correct choice when clicking second button", () => {
    const onSelect = vi.fn();
    render(<ChoiceButtons choices={choices} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("有差异"));
    expect(onSelect).toHaveBeenCalledWith("有差异");
  });

  it("disables all buttons when disabled=true", () => {
    const onSelect = vi.fn();
    render(
      <ChoiceButtons choices={choices} onSelect={onSelect} disabled />
    );
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
    fireEvent.click(buttons[0]);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("renders single choice correctly", () => {
    render(
      <ChoiceButtons choices={["✅ 准备好了，开始吧"]} onSelect={() => {}} />
    );
    expect(screen.getByText("✅ 准备好了，开始吧")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("renders four choices correctly", () => {
    const fourChoices = ["A", "B", "C", "D"];
    render(<ChoiceButtons choices={fourChoices} onSelect={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(4);
  });
});
