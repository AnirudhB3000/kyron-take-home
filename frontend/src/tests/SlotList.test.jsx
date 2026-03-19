import { render, screen } from "@testing-library/react";

import SlotList from "../components/SlotList";

describe("SlotList", () => {
  test("renders available appointment buttons", () => {
    render(
      <SlotList
        slots={[
          {
            slot_id: "slot-1",
            start_at: "2026-03-24T09:00:00",
            appointment_type: "new_patient_consult",
          },
        ]}
        onSelect={() => {}}
        disabled={false}
        selectedWeekday="tuesday"
      />,
    );

    expect(screen.getByText("Select an appointment")).toBeInTheDocument();
    expect(screen.getByText(/current tuesday view/i)).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  test("shows the pending state for the selected slot", () => {
    render(
      <SlotList
        slots={[
          {
            slot_id: "slot-1",
            start_at: "2026-03-24T09:00:00",
            appointment_type: "new_patient_consult",
          },
        ]}
        onSelect={() => {}}
        disabled={false}
        pendingSlotId="slot-1"
        selectedWeekday={null}
      />,
    );

    expect(screen.getByText("Awaiting confirmation")).toBeInTheDocument();
  });
});
