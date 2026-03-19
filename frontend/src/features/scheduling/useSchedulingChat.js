import { useEffect, useState } from "react";

import {
  bookAppointment,
  createConversation,
  listSlots,
  matchProvider,
  processTurn,
  startVoiceHandoff,
  updateIntake,
} from "../../services/schedulingApi";
import {
  fetchOfficeAddress,
  fetchOfficeHours,
  submitRefillRequest,
} from "../../services/systemApi";

const INTRO_MESSAGE =
  "Hello, I'm Kyron Medical's scheduling assistant. I can help book an appointment, share office information, and continue by phone if needed.";

const FIELD_PROMPTS = {
  first_name: "To get started, what is your first name?",
  last_name: "Thanks. What is your last name?",
  date_of_birth: "What is your date of birth? Please use YYYY-MM-DD.",
  phone_number: "What is your phone number?",
  email: "What is your email address?",
  appointment_reason: "What body part or issue would you like to be seen for?",
};

const SMS_OPT_IN_PROMPT =
  "Would you like text updates about your scheduling request at this number? Reply yes or no.";

const FIELD_ERROR_PREFIX = {
  first_name: "That first name does not look valid.",
  last_name: "That last name does not look valid.",
  date_of_birth: "That date of birth is not valid.",
  phone_number: "That phone number is not valid.",
  email: "That email address is not valid.",
  appointment_reason: "I still need a clearer appointment reason.",
};

const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

const AFFIRMATIVE_CONFIRMATIONS = ["yes", "confirm", "book it", "that works", "works", "schedule it"];
const NEGATIVE_CONFIRMATIONS = ["no", "cancel", "different time", "another slot"];
const OFFICE_HOURS_HINTS = ["office hours", "hours", "when are you open", "when do you open", "when do you close"];
const OFFICE_ADDRESS_HINTS = ["address", "located", "where are you", "where is the office", "office location"];
const REFILL_HINTS = ["refill", "prescription help", "medication refill", "check my refill"];

function createMessage(role, content) {
  return {
    id: `${role}-${crypto.randomUUID()}`,
    role,
    content,
  };
}

function extractWeekday(text) {
  const normalized = text.toLowerCase();
  return WEEKDAYS.find((weekday) => normalized.includes(weekday)) || null;
}

function formatSlot(slot) {
  const start = new Date(slot.start_at);
  return start.toLocaleString([], {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function buildRetryMessage(field, errorMessage) {
  const prefix = FIELD_ERROR_PREFIX[field] || "That response is not valid yet.";
  const prompt = FIELD_PROMPTS[field] || "Please try again.";
  return `${prefix} ${errorMessage} ${prompt}`;
}

function isAffirmative(text) {
  const normalized = text.trim().toLowerCase();
  return AFFIRMATIVE_CONFIRMATIONS.some((item) => normalized.includes(item));
}

function isNegative(text) {
  const normalized = text.trim().toLowerCase();
  return NEGATIVE_CONFIRMATIONS.some((item) => normalized.includes(item));
}

function isOfficeHoursQuestion(text) {
  const normalized = text.trim().toLowerCase();
  return OFFICE_HOURS_HINTS.some((hint) => normalized.includes(hint));
}

function isOfficeAddressQuestion(text) {
  const normalized = text.trim().toLowerCase();
  return OFFICE_ADDRESS_HINTS.some((hint) => normalized.includes(hint));
}

function isRefillQuestion(text) {
  const normalized = text.trim().toLowerCase();
  return REFILL_HINTS.some((hint) => normalized.includes(hint));
}

function appendPromptIfNeeded(message, field) {
  const prompt = FIELD_PROMPTS[field];
  return prompt ? `${message} ${prompt}` : message;
}

export function useSchedulingChat() {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([
    createMessage("assistant", INTRO_MESSAGE),
    createMessage("assistant", FIELD_PROMPTS.first_name),
  ]);
  const [missingFields, setMissingFields] = useState([]);
  const [activeField, setActiveField] = useState("first_name");
  const [slots, setSlots] = useState([]);
  const [pendingSlotId, setPendingSlotId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [handoffSubmitting, setHandoffSubmitting] = useState(false);
  const [workflowStep, setWorkflowStep] = useState("intake");
  const [selectedWeekday, setSelectedWeekday] = useState(null);
  const [canContinueByPhone, setCanContinueByPhone] = useState(false);
  const [awaitingSmsOptIn, setAwaitingSmsOptIn] = useState(false);

  useEffect(() => {
    let active = true;

    async function initialize() {
      try {
        const response = await createConversation();
        if (!active) {
          return;
        }
        setConversationId(response.conversation_id);
        setMissingFields(response.missing_fields);
        setActiveField(response.active_field || response.missing_fields[0] || null);
        setWorkflowStep(response.workflow_step);
      } catch {
        if (active) {
          setMessages((current) => [
            ...current,
            createMessage(
              "assistant",
              "The scheduling system is unavailable right now. Please try again shortly.",
            ),
          ]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    initialize();

    return () => {
      active = false;
    };
  }, []);

  async function advanceFromCompletedIntake() {
    const matchResponse = await matchProvider(conversationId);
    if (!matchResponse.matched) {
      setActiveField("appointment_reason");
      setSlots([]);
      setWorkflowStep("provider_matching");
      setMessages((current) => [...current, createMessage("assistant", matchResponse.reason)]);
      return;
    }

    const slotResponse = await listSlots(conversationId);
    setActiveField(null);
    setWorkflowStep("slot_selection");
    setSlots(slotResponse.slots);
    setMessages((current) => [
      ...current,
      createMessage(
        "assistant",
        `I matched you with ${matchResponse.provider_name} in ${matchResponse.specialty}. Please choose one of the available appointments below, or ask for a specific weekday.`,
      ),
    ]);
  }

  async function handleSmsOptInChoice(trimmedInput) {
    let wantsSms = null;
    if (isAffirmative(trimmedInput)) {
      wantsSms = true;
    } else if (isNegative(trimmedInput)) {
      wantsSms = false;
    }

    if (wantsSms === null) {
      setMessages((current) => [
        ...current,
        createMessage("assistant", SMS_OPT_IN_PROMPT),
      ]);
      return;
    }

    const response = await updateIntake(conversationId, { sms_opt_in: wantsSms });
    setAwaitingSmsOptIn(false);
    setMissingFields(response.missing_fields);
    setActiveField(response.active_field || response.missing_fields[0] || null);
    setWorkflowStep(response.workflow_step);

    if (response.missing_fields.length) {
      const nextField = response.active_field || response.missing_fields[0];
      const leadIn = wantsSms
        ? "Thanks. I'll send text updates to this number."
        : "No problem. I won't send text updates.";
      setMessages((current) => [
        ...current,
        createMessage("assistant", `${leadIn} ${FIELD_PROMPTS[nextField]}`),
      ]);
      return;
    }

    await advanceFromCompletedIntake();
  }

  async function submitUserMessage(input) {
    if (!conversationId || !input.trim()) {
      return;
    }

    const trimmedInput = input.trim();
    const currentField = activeField || missingFields[0];
    setSubmitting(true);
    setMessages((current) => [...current, createMessage("user", trimmedInput)]);

    try {
      if (pendingSlotId) {
        if (isAffirmative(trimmedInput)) {
          await confirmPendingSlot();
          return;
        }
        if (isNegative(trimmedInput)) {
          setPendingSlotId(null);
          setMessages((current) => [
            ...current,
            createMessage("assistant", "No problem. Please choose a different appointment time below or ask for a specific weekday."),
          ]);
          return;
        }
        setMessages((current) => [
          ...current,
          createMessage("assistant", "Please reply yes to confirm that appointment, or no if you want a different time."),
        ]);
        return;
      }

      if (awaitingSmsOptIn) {
        await handleSmsOptInChoice(trimmedInput);
        return;
      }

      if (isOfficeHoursQuestion(trimmedInput)) {
        const hours = await fetchOfficeHours();
        const hoursMessage = `${hours.weekdays.join(" ")} ${hours.saturday} ${hours.sunday}`;
        setMessages((current) => [
          ...current,
          createMessage("assistant", appendPromptIfNeeded(hoursMessage, currentField)),
        ]);
        return;
      }

      if (isOfficeAddressQuestion(trimmedInput)) {
        const address = await fetchOfficeAddress();
        const addressMessage = `${address.practice_name} is located at ${address.street}, ${address.city}, ${address.state} ${address.postal_code}. The main office line is ${address.phone_number}.`;
        setMessages((current) => [
          ...current,
          createMessage("assistant", appendPromptIfNeeded(addressMessage, currentField)),
        ]);
        return;
      }

      if (isRefillQuestion(trimmedInput)) {
        const refillResponse = await submitRefillRequest(trimmedInput);
        setMessages((current) => [
          ...current,
          createMessage("assistant", appendPromptIfNeeded(refillResponse.assistant_message, currentField)),
        ]);
        return;
      }

      const weekday = extractWeekday(trimmedInput);
      if (workflowStep === "slot_selection" && weekday) {
        const slotResponse = await listSlots(conversationId, weekday);
        setSelectedWeekday(weekday);
        setSlots(slotResponse.slots);
        setMessages((current) => [
          ...current,
          createMessage(
            "assistant",
            slotResponse.slots.length
              ? `Here are the available ${weekday} appointments with ${slotResponse.provider_name}.`
              : `I do not have any ${weekday} appointments available right now.`,
          ),
        ]);
        return;
      }

      if (!currentField) {
        return;
      }

      const turnResponse = await processTurn(conversationId, trimmedInput);
      if (turnResponse.handled) {
        setActiveField(turnResponse.active_field || currentField);
        setWorkflowStep(turnResponse.workflow_step);
        if (turnResponse.assistant_message) {
          setMessages((current) => [
            ...current,
            createMessage("assistant", turnResponse.assistant_message),
          ]);
        }
        return;
      }

      const response = await updateIntake(conversationId, { [currentField]: trimmedInput });
      setMissingFields(response.missing_fields);
      setActiveField(response.active_field || response.missing_fields[0] || null);
      setWorkflowStep(response.workflow_step);
      if (currentField === "phone_number") {
        setCanContinueByPhone(true);
        setAwaitingSmsOptIn(true);
        setMessages((current) => [...current, createMessage("assistant", SMS_OPT_IN_PROMPT)]);
        return;
      }

      if (response.missing_fields.length) {
        const nextField = response.active_field || response.missing_fields[0];
        setMessages((current) => [...current, createMessage("assistant", FIELD_PROMPTS[nextField])]);
        return;
      }

      await advanceFromCompletedIntake();
    } catch (error) {
      setMessages((current) => [
        ...current,
        createMessage("assistant", buildRetryMessage(currentField, error.message || "Please try again.")),
      ]);
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmPendingSlot() {
    const slotId = pendingSlotId;
    if (!conversationId || !slotId) {
      return;
    }

    const response = await bookAppointment(conversationId, slotId);
    setPendingSlotId(null);
    setWorkflowStep(response.workflow_step);
    setMessages((current) => [
      ...current,
      createMessage(
        "assistant",
        `${response.confirmation_message} You are all set for ${formatSlot(
          slots.find((slot) => slot.slot_id === slotId),
        )}.`,
      ),
    ]);
    setSlots([]);
  }

  async function selectSlot(slotId) {
    const slot = slots.find((item) => item.slot_id === slotId);
    if (!slot) {
      return;
    }

    setPendingSlotId(slotId);
    setMessages((current) => [
      ...current,
      createMessage(
        "assistant",
        `You selected ${formatSlot(slot)}. Reply yes to confirm this appointment, or no if you want a different time.`,
      ),
    ]);
  }

  async function startPhoneHandoff() {
    if (!conversationId) {
      return;
    }
    if (!canContinueByPhone) {
      setMessages((current) => [
        ...current,
        createMessage(
          "assistant",
          "I need your phone number before I can continue by phone.",
        ),
      ]);
      return;
    }

    setHandoffSubmitting(true);
    try {
      const response = await startVoiceHandoff(conversationId);
      setMessages((current) => [
        ...current,
        createMessage("assistant", response.assistant_message),
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        createMessage(
          "assistant",
          error.message || "I could not prepare the phone handoff right now.",
        ),
      ]);
    } finally {
      setHandoffSubmitting(false);
    }
  }

  return {
    activeField,
    canContinueByPhone,
    handoffSubmitting,
    loading,
    pendingSlotId,
    submitting,
    messages,
    slots,
    workflowStep,
    selectedWeekday,
    submitUserMessage,
    selectSlot,
    startPhoneHandoff,
  };
}
