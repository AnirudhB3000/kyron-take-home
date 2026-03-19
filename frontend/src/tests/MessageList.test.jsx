import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import MessageList from "../components/MessageList";

describe("MessageList", () => {
  test("scrolls to the latest message when messages change", () => {
    const scrollIntoView = vi.fn();

    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;

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

    expect(scrollIntoView).toHaveBeenCalled();
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
