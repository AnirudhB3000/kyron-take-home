import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import AppShell from "../app/AppShell";
import { useSchedulingChat } from "../features/scheduling/useSchedulingChat";

vi.mock("../services/systemApi", () => ({
  fetchSystemStatus: vi.fn().mockResolvedValue({
    label: "online",
    tone: "success",
  }),
}));

vi.mock("../features/scheduling/useSchedulingChat", () => ({
  useSchedulingChat: vi.fn(),
}));

const defaultHookState = {
  activeField: "first_name",
  canContinueByPhone: false,
  handoffSubmitting: false,
  loading: false,
  pendingSlotId: null,
  selectedWeekday: null,
  submitting: false,
  messages: [
    {
      id: "assistant-1",
      role: "assistant",
      content: "Hello, I’m Kyron Medical’s scheduling assistant.",
    },
  ],
  slots: [],
  startPhoneHandoff: vi.fn(),
  submitUserMessage: vi.fn(),
  selectSlot: vi.fn(),
  workflowStep: "intake",
};

describe("AppShell", () => {
  beforeEach(() => {
    vi.mocked(useSchedulingChat).mockReturnValue({ ...defaultHookState });
  });

  test("renders the patient assistant shell", async () => {
    render(<AppShell />);

    expect(
      screen.getByText("AI concierge for modern patient access"),
    ).toBeInTheDocument();
    expect(screen.getByText("Patient conversation")).toBeInTheDocument();
    expect(screen.getByText("Current step")).toBeInTheDocument();
    expect(screen.getAllByText("Patient intake").length).toBeGreaterThan(0);
    expect(screen.getByText(/Kyron Medical’s scheduling assistant/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("online").length).toBeGreaterThan(0);
    });

    expect(
      screen.getByRole("button", { name: "Continue by phone" }),
    ).toBeDisabled();
  });

  test("enables the phone button when handoff is allowed", async () => {
    vi.mocked(useSchedulingChat).mockReturnValue({
      ...defaultHookState,
      canContinueByPhone: true,
    });

    render(<AppShell />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Continue by phone" })).toBeEnabled();
    });
  });
});
