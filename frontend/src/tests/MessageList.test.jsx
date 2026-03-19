import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import MessageList from "../components/MessageList";

describe("MessageList", () => {
  test("scrolls the chat container to the latest message when messages change", () => {
    const scrollTo = vi.fn();

    Object.defineProperty(window.HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get: () => 240,
    });
    window.HTMLElement.prototype.scrollTo = scrollTo;

    const { rerender } = render(
      <MessageList
        messages={[
          { id: "1", role: "assistant", content: "Welcome to Kyron." },
        ]}
      />,
    );

    rerender(
      <MessageList
        messages={[
          { id: "1", role: "assistant", content: "Welcome to Kyron." },
          { id: "2", role: "assistant", content: "What is your first name?" },
        ]}
      />,
    );

    expect(scrollTo).toHaveBeenCalledWith({ top: 240, behavior: "smooth" });
  });

  test("renders assistant messages", () => {
    render(
      <MessageList
        messages={[
          { id: "1", role: "assistant", content: "Welcome to Kyron." },
        ]}
      />,
    );

    expect(screen.getByText("Welcome to Kyron.")).toBeInTheDocument();
  });
});
