import ChatComposer from "../components/ChatComposer";
import ChatHeader from "../components/ChatHeader";
import MessageList from "../components/MessageList";
import SlotList from "../components/SlotList";
import { useSchedulingChat } from "../features/scheduling/useSchedulingChat";
import { fetchSystemStatus } from "../services/systemApi";

import { useEffect, useState } from "react";

const DEFAULT_STATUS = {
  label: "checking",
  tone: "neutral",
};

const WORKFLOW_LABELS = {
  intake: "Patient intake",
  provider_matching: "Provider matching",
  slot_selection: "Appointment selection",
  booking_confirmation: "Booking confirmation",
  completed: "Confirmed",
};

const FIELD_LABELS = {
  first_name: "First name",
  last_name: "Last name",
  date_of_birth: "Date of birth",
  phone_number: "Phone number",
  email: "Email address",
  appointment_reason: "Appointment reason",
};

function getWorkflowCopy(workflowStep, activeField) {
  if (workflowStep === "completed") {
    return {
      eyebrow: "Confirmed",
      title: "The appointment flow is complete.",
      detail: "The chat remains open for follow-up questions, office information, and phone handoff.",
    };
  }

  if (workflowStep === "slot_selection") {
    return {
      eyebrow: "Decision point",
      title: "Review available times and confirm one slot.",
      detail: "The assistant keeps the matched specialty and weekday refinements in context while you choose.",
    };
  }

  if (workflowStep === "provider_matching") {
    return {
      eyebrow: "Routing",
      title: "The assistant is narrowing the request to the right specialist.",
      detail: "If the concern is unclear or unsupported, the system should recover and ask for a clearer body part or issue.",
    };
  }

  return {
    eyebrow: "Guided intake",
    title: activeField
      ? `The current step is collecting the patient's ${FIELD_LABELS[activeField].toLowerCase()}.`
      : "The assistant is collecting the remaining patient details.",
    detail: "Short detours like office hours, address questions, and refill requests should be answered without losing this step.",
  };
}

export default function AppShell() {
  const [status, setStatus] = useState(DEFAULT_STATUS);
  const {
    activeField,
    canContinueByPhone,
    handoffSubmitting,
    loading,
    pendingSlotId,
    selectedWeekday,
    submitting,
    messages,
    slots,
    startPhoneHandoff,
    submitUserMessage,
    selectSlot,
    workflowStep,
  } = useSchedulingChat();

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      const nextStatus = await fetchSystemStatus();

      if (!cancelled) {
        setStatus(nextStatus);
      }
    }

    loadStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  const workflowCopy = getWorkflowCopy(workflowStep, activeField);
  const selectedWeekdayLabel = selectedWeekday
    ? `${selectedWeekday.slice(0, 1).toUpperCase()}${selectedWeekday.slice(1)} filter active`
    : "No weekday filter";
  const transcriptState = loading
    ? "Syncing the conversation workspace."
    : submitting || handoffSubmitting
      ? "Processing the latest patient action."
      : "Conversation ready for the next patient reply.";

  return (
    <main className="app-shell">
      <section className="hero-panel glass-panel">
        <div className="glow-orb glow-orb-a" aria-hidden="true" />
        <div className="glow-orb glow-orb-b" aria-hidden="true" />
        <p className="eyebrow">Kyron Medical</p>
        <h1>AI concierge for modern patient access</h1>
        <p className="lede">
          A fluid front desk experience for appointments, follow-up questions,
          and seamless transition into voice.
        </p>
        <div className="hero-metrics">
          <div className="metric-card glass-card">
            <span className="metric-label">Primary focus</span>
            <strong>Scheduling</strong>
          </div>
          <div className="metric-card glass-card">
            <span className="metric-label">Channel continuity</span>
            <strong>Chat to voice</strong>
          </div>
          <div className="metric-card glass-card">
            <span className="metric-label">Conversation state</span>
            <strong>{WORKFLOW_LABELS[workflowStep] || "Patient intake"}</strong>
          </div>
        </div>
        <div className="hero-story glass-card">
          <p className="section-kicker">{workflowCopy.eyebrow}</p>
          <h2>{workflowCopy.title}</h2>
          <p>{workflowCopy.detail}</p>
        </div>
      </section>
      <section className="chat-panel glass-panel" aria-label="Chat workspace">
        <ChatHeader
          status={status}
          onContinueByPhone={startPhoneHandoff}
          phoneDisabled={!canContinueByPhone || loading || submitting}
          handoffSubmitting={handoffSubmitting}
          workflowLabel={WORKFLOW_LABELS[workflowStep] || "Patient intake"}
        />
        <section className="conversation-state" aria-label="Conversation status">
          <article className="state-card glass-card">
            <p className="section-kicker">Current step</p>
            <h3>{WORKFLOW_LABELS[workflowStep] || "Patient intake"}</h3>
            <p>
              {activeField
                ? `Waiting on: ${FIELD_LABELS[activeField] || activeField}`
                : "The workflow has the information it needs for the current step."}
            </p>
          </article>
          <article className="state-card glass-card">
            <p className="section-kicker">Slot view</p>
            <h3>{slots.length ? `${slots.length} options ready` : "No slots displayed"}</h3>
            <p>{selectedWeekdayLabel}</p>
          </article>
          <article className="state-card glass-card">
            <p className="section-kicker">System posture</p>
            <h3>{status.label}</h3>
            <p>{transcriptState}</p>
          </article>
        </section>
        <MessageList messages={messages} />
        <SlotList
          slots={slots}
          onSelect={selectSlot}
          disabled={submitting}
          pendingSlotId={pendingSlotId}
          selectedWeekday={selectedWeekday}
        />
        <ChatComposer
          disabled={loading || submitting || handoffSubmitting}
          onSubmit={submitUserMessage}
          workflowLabel={WORKFLOW_LABELS[workflowStep] || "Patient intake"}
          activeField={activeField}
        />
      </section>
    </main>
  );
}
