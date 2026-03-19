import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import ChatHeader from "../components/ChatHeader";

describe("ChatHeader", () => {
  test("renders the system status badge", () => {
    render(
      <ChatHeader
        status={{ label: "online", tone: "success" }}
        onContinueByPhone={() => {}}
        phoneDisabled
        handoffSubmitting={false}
        workflowLabel="Patient intake"
      />,
    );

    expect(screen.getByText("Patient conversation")).toBeInTheDocument();
    expect(screen.getByText(/assistant should stay calm/i)).toBeInTheDocument();
    expect(screen.getByText("online")).toBeInTheDocument();
  });

  test("invokes phone handoff when enabled", () => {
    const onContinueByPhone = vi.fn();

    render(
      <ChatHeader
        status={{ label: "online", tone: "success" }}
        onContinueByPhone={onContinueByPhone}
        phoneDisabled={false}
        handoffSubmitting={false}
        workflowLabel="Patient intake"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Continue by phone" }));

    expect(onContinueByPhone).toHaveBeenCalledTimes(1);
  });
});
