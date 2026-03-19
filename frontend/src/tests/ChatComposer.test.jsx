import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import ChatComposer from "../components/ChatComposer";

describe("ChatComposer", () => {
  test("submits when Enter is pressed", () => {
    const onSubmit = vi.fn();

    render(
      <ChatComposer
        disabled={false}
        onSubmit={onSubmit}
        workflowLabel="Patient intake"
        activeField="first_name"
      />,
    );

    const input = screen.getByRole("textbox", { name: /tell us how we can help/i });

    fireEvent.change(input, { target: { value: "Jordan" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(onSubmit).toHaveBeenCalledWith("Jordan");
  });

  test("preserves newline behavior for Shift+Enter", () => {
    const onSubmit = vi.fn();

    render(
      <ChatComposer
        disabled={false}
        onSubmit={onSubmit}
        workflowLabel="Patient intake"
        activeField="appointment_reason"
      />,
    );

    const input = screen.getByRole("textbox", { name: /tell us how we can help/i });

    fireEvent.change(input, { target: { value: "Line one" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter", shiftKey: true });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
