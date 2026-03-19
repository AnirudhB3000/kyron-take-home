import { act, renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { useSchedulingChat } from "../features/scheduling/useSchedulingChat";
import * as schedulingApi from "../services/schedulingApi";
import * as systemApi from "../services/systemApi";

vi.mock("../services/schedulingApi", () => ({
  createConversation: vi.fn(),
  processTurn: vi.fn(),
  updateIntake: vi.fn(),
  matchProvider: vi.fn(),
  listSlots: vi.fn(),
  bookAppointment: vi.fn(),
  startVoiceHandoff: vi.fn(),
}));

vi.mock("../services/systemApi", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchOfficeHours: vi.fn(),
    fetchOfficeAddress: vi.fn(),
    submitRefillRequest: vi.fn(),
  };
});

const SLOT_FIXTURE = [
  {
    slot_id: "slot-1",
    start_at: "2026-03-24T09:00:00",
    appointment_type: "new_patient_consult",
  },
  {
    slot_id: "slot-2",
    start_at: "2026-03-25T13:30:00",
    appointment_type: "follow_up",
  },
];

describe("useSchedulingChat", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "first_name",
      workflow_step: "intake",
    });
  });

  test("introduces the assistant before intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["first_name"],
      active_field: "first_name",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.messages[0].content).toMatch(/Kyron Medical's scheduling assistant|Kyron Medical’s scheduling assistant/);
    expect(result.current.messages[1].content).toMatch(/first name/i);
  });

  test("uses backend clarification handling and returns to intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["last_name"],
      active_field: "last_name",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: true,
      turn_type: "clarification_question",
      assistant_message: "This is Kyron Medical's virtual scheduling assistant. Thanks. What is your last name?",
      active_field: "last_name",
      workflow_step: "intake",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("what are you?");
    });

    expect(schedulingApi.processTurn).toHaveBeenCalledWith("conversation-1", "what are you?");
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1).content).toMatch(/virtual scheduling assistant/i);
    expect(result.current.messages.at(-1).content).toMatch(/last name/i);
  });

  test("uses backend clarification handling for site questions", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["first_name"],
      active_field: "first_name",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: true,
      turn_type: "clarification_question",
      assistant_message:
        "This is Kyron Medical's virtual scheduling assistant. I collect a few details to find the right appointment. To get started, what is your first name?",
      active_field: "first_name",
      workflow_step: "intake",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("please tell me how this works?");
    });

    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1).content).toMatch(/find the right appointment/i);
    expect(result.current.messages.at(-1).content).toMatch(/first name/i);
  });

  test("answers office hours questions without advancing intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["first_name"],
      active_field: "first_name",
    });
    systemApi.fetchOfficeHours.mockResolvedValue({
      weekdays: ["Monday to Thursday: 8:00 AM to 5:30 PM", "Friday: 8:00 AM to 4:00 PM"],
      saturday: "Saturday: Urgent scheduling callbacks only from 9:00 AM to 12:00 PM",
      sunday: "Sunday: Closed",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("What are your office hours?");
    });

    expect(systemApi.fetchOfficeHours).toHaveBeenCalled();
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.activeField).toBe("first_name");
    expect(result.current.messages.at(-1).content).toMatch(/Monday to Thursday/i);
    expect(result.current.messages.at(-1).content).toMatch(/what is your first name/i);
  });

  test("answers office address questions without advancing intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["last_name"],
      active_field: "last_name",
    });
    systemApi.fetchOfficeAddress.mockResolvedValue({
      practice_name: "Kyron Medical Downtown Clinic",
      street: "1450 Market Street, Suite 600",
      city: "San Francisco",
      state: "CA",
      postal_code: "94103",
      phone_number: "(415) 555-0112",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("What is your address?");
    });

    expect(systemApi.fetchOfficeAddress).toHaveBeenCalled();
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.activeField).toBe("last_name");
    expect(result.current.messages.at(-1).content).toMatch(/1450 Market Street/i);
    expect(result.current.messages.at(-1).content).toMatch(/what is your last name/i);
  });

  test("answers refill questions without advancing intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["email"],
      active_field: "email",
    });
    systemApi.submitRefillRequest.mockResolvedValue({
      assistant_message:
        "I can help start a prescription refill request, but I cannot verify live refill status or provide medication advice here. A staff member would follow up using the contact information on file.",
      workflow_type: "refill_request",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("I need a refill for my inhaler");
    });

    expect(systemApi.submitRefillRequest).toHaveBeenCalledWith("I need a refill for my inhaler");
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.activeField).toBe("email");
    expect(result.current.messages.at(-1).content).toMatch(/cannot verify live refill status/i);
    expect(result.current.messages.at(-1).content).toMatch(/what is your email address/i);
  });

  test("answers field-specific clarification questions without advancing", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["phone_number"],
      active_field: "phone_number",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: true,
      turn_type: "clarification_question",
      assistant_message:
        "I ask for your phone number so I can continue by phone if needed and send scheduling updates. What is your phone number?",
      active_field: "phone_number",
      workflow_step: "intake",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("why do you need my phone number?");
    });

    expect(result.current.activeField).toBe("phone_number");
    expect(result.current.messages.at(-1).content).toMatch(/phone number/i);
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
  });

  test("renders backend emergency guidance without advancing intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: true,
      turn_type: "emergency",
      assistant_message: "I cannot help with an emergency in chat. Please call emergency services now.",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("i died 7 minutes ago");
    });

    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.activeField).toBe("appointment_reason");
    expect(result.current.messages.at(-1).content).toMatch(/emergency/i);
  });

  test("renders backend medical-advice guidance without advancing intake", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: true,
      turn_type: "medical_advice",
      assistant_message: "I can help with scheduling, but I cannot provide medical advice or diagnosis.",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("what medication should I take?");
    });

    expect(result.current.activeField).toBe("appointment_reason");
    expect(schedulingApi.updateIntake).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1).content).toMatch(/cannot provide medical advice/i);
  });

  test("keeps the user on the same field after invalid input", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["date_of_birth"],
      active_field: "date_of_birth",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "date_of_birth",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockRejectedValue(
      new Error("Please enter a valid date of birth in YYYY-MM-DD format."),
    );

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("ghguejdi");
    });

    expect(result.current.activeField).toBe("date_of_birth");
    expect(result.current.messages.at(-1).content).toMatch(/date of birth is not valid/i);
  });

  test("unsupported appointment reasons stay retryable", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflowStep: "intake",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "provider_matching",
      missing_fields: [],
      active_field: null,
    });
    schedulingApi.matchProvider.mockResolvedValue({
      matched: false,
      reason:
        "I could not match that concern to a supported specialty yet. Please describe the body part or issue in different words, such as knee, skin rash, blurry vision, or sinus pain.",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("stomach pain");
    });

    expect(result.current.activeField).toBe("appointment_reason");
    expect(result.current.messages.at(-1).content).toMatch(/describe the body part or issue in different words/i);
  });

  test("can recover from unsupported concern to corrected concern and show slots", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake
      .mockResolvedValueOnce({
        conversation_id: "conversation-1",
        workflow_step: "provider_matching",
        missing_fields: [],
        active_field: null,
      })
      .mockResolvedValueOnce({
        conversation_id: "conversation-1",
        workflow_step: "provider_matching",
        missing_fields: [],
        active_field: null,
      });
    schedulingApi.matchProvider
      .mockResolvedValueOnce({
        matched: false,
        reason:
          "I could not match that concern to a supported specialty yet. Please describe the body part or issue in different words, such as knee, skin rash, blurry vision, or sinus pain.",
      })
      .mockResolvedValueOnce({
        matched: true,
        provider_name: "Dr. Olivia Bennett",
        specialty: "Orthopedics",
      });
    schedulingApi.listSlots.mockResolvedValue({ slots: SLOT_FIXTURE, provider_name: "Dr. Olivia Bennett" });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("stomach pain");
    });

    await act(async () => {
      await result.current.submitUserMessage("knee pain");
    });

    expect(schedulingApi.listSlots).toHaveBeenCalledWith("conversation-1");
    expect(result.current.slots).toHaveLength(2);
    expect(result.current.messages.at(-1).content).toMatch(/matched you with dr\. olivia bennett/i);
  });

  test("updates slots when the patient asks for a weekday", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "slot_selection",
      missing_fields: [],
      active_field: null,
    });
    schedulingApi.listSlots.mockResolvedValue({
      provider_name: "Dr. Olivia Bennett",
      slots: [SLOT_FIXTURE[1]],
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("Do you have something on Tuesday?");
    });

    expect(schedulingApi.listSlots).toHaveBeenCalledWith("conversation-1", "tuesday");
    expect(result.current.selectedWeekday).toBe("tuesday");
    expect(result.current.slots).toEqual([SLOT_FIXTURE[1]]);
  });

  test("requires confirmation before booking a selected slot", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "provider_matching",
      missing_fields: [],
      active_field: null,
    });
    schedulingApi.matchProvider.mockResolvedValue({
      matched: true,
      provider_name: "Dr. Olivia Bennett",
      specialty: "Orthopedics",
    });
    schedulingApi.listSlots.mockResolvedValue({ slots: SLOT_FIXTURE });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("broken knee");
    });

    await act(async () => {
      result.current.selectSlot("slot-1");
    });

    expect(schedulingApi.bookAppointment).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1).content).toMatch(/reply yes to confirm/i);
  });

  test("confirms a selected slot after explicit yes", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["appointment_reason"],
      active_field: "appointment_reason",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "appointment_reason",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "provider_matching",
      missing_fields: [],
      active_field: null,
    });
    schedulingApi.matchProvider.mockResolvedValue({
      matched: true,
      provider_name: "Dr. Olivia Bennett",
      specialty: "Orthopedics",
    });
    schedulingApi.listSlots.mockResolvedValue({ slots: SLOT_FIXTURE });
    schedulingApi.bookAppointment.mockResolvedValue({
      workflow_step: "completed",
      confirmation_message: "Your appointment has been booked successfully.",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("broken knee");
    });

    await act(async () => {
      result.current.selectSlot("slot-1");
    });

    await act(async () => {
      await result.current.submitUserMessage("yes");
    });

    expect(schedulingApi.bookAppointment).toHaveBeenCalledWith("conversation-1", "slot-1");
  });

  test("asks about text updates immediately after collecting a phone number", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["phone_number"],
      active_field: "phone_number",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "phone_number",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["email"],
      active_field: "email",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("555-123-4567");
    });

    expect(result.current.canContinueByPhone).toBe(true);
    expect(result.current.messages.at(-1).content).toMatch(/text updates/i);
    expect(result.current.messages.at(-1).content).toMatch(/reply yes or no/i);
  });

  test("stores sms opt-in before moving to the next intake field", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["phone_number"],
      active_field: "phone_number",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "phone_number",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake
      .mockResolvedValueOnce({
        conversation_id: "conversation-1",
        workflow_step: "intake",
        missing_fields: ["email"],
        active_field: "email",
      })
      .mockResolvedValueOnce({
        conversation_id: "conversation-1",
        workflow_step: "intake",
        missing_fields: ["email"],
        active_field: "email",
      });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("555-123-4567");
    });

    await act(async () => {
      await result.current.submitUserMessage("yes");
    });

    expect(schedulingApi.updateIntake).toHaveBeenNthCalledWith(1, "conversation-1", { phone_number: "555-123-4567" });
    expect(schedulingApi.updateIntake).toHaveBeenNthCalledWith(2, "conversation-1", { sms_opt_in: true });
    expect(result.current.messages.at(-1).content).toMatch(/send text updates to this number/i);
    expect(result.current.messages.at(-1).content).toMatch(/email address/i);
  });

  test("guards phone handoff until a phone number is collected", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["first_name"],
      active_field: "first_name",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.startPhoneHandoff();
    });

    expect(schedulingApi.startVoiceHandoff).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1).content).toMatch(/need your phone number/i);
  });

  test("creates a phone handoff once a phone number is available", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["phone_number"],
      active_field: "phone_number",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "phone_number",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["email"],
      active_field: "email",
    });
    schedulingApi.startVoiceHandoff.mockResolvedValue({
      handoff_id: "handoff-1",
      assistant_message: "I am ready to continue by phone. The voice handoff has been prepared and would call 555-123-4567 with your current scheduling context.",
    });

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("555-123-4567");
    });

    expect(result.current.canContinueByPhone).toBe(true);

    await act(async () => {
      await result.current.startPhoneHandoff();
    });

    expect(schedulingApi.startVoiceHandoff).toHaveBeenCalledWith("conversation-1");
    expect(result.current.messages.at(-1).content).toMatch(/ready to continue by phone/i);
  });

  test("renders a clean handoff error message", async () => {
    schedulingApi.createConversation.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["phone_number"],
      active_field: "phone_number",
    });
    schedulingApi.processTurn.mockResolvedValue({
      handled: false,
      turn_type: "field_answer",
      active_field: "phone_number",
      workflow_step: "intake",
    });
    schedulingApi.updateIntake.mockResolvedValue({
      conversation_id: "conversation-1",
      workflow_step: "intake",
      missing_fields: ["email"],
      active_field: "email",
    });
    schedulingApi.startVoiceHandoff.mockRejectedValue(
      new Error("Unable to prepare the phone handoff right now."),
    );

    const { result } = renderHook(() => useSchedulingChat());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.submitUserMessage("555-123-4567");
    });

    await act(async () => {
      await result.current.startPhoneHandoff();
    });

    expect(result.current.messages.at(-1).content).toMatch(/unable to prepare the phone handoff right now/i);
  });
});
