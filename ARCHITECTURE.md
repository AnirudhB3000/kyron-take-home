# Architecture

## Core Architectural Considerations

This application should be built as a conversation-centric system. The patient should experience a single assistant across web chat and voice, while the backend owns all state, workflow logic, and integrations.

### Frontend

The frontend should be a React.js application responsible only for the user interface. It should handle:

- chat presentation
- intake data entry
- appointment slot selection
- triggering the voice handoff flow

The frontend should not contain business logic and should not call the LLM directly.

### Backend

The backend should be a FastAPI application that acts as the system orchestrator. It should own:

- conversation state
- patient state
- workflow progression
- provider matching
- appointment slot retrieval and filtering
- booking
- notification triggers
- chat-to-voice handoff
- safety enforcement

The backend should be the source of truth for all actions and decisions.

### LLM Usage

The LLM should be used in a constrained agent-with-tools pattern.

The LLM should handle:

- understanding patient intent
- extracting structured information from free-text messages
- selecting the next allowed action
- generating natural language responses
- summarizing context for voice handoff

The backend should handle:

- validating all requested actions
- executing deterministic logic
- preserving state
- preventing unsupported or unsafe behavior

The LLM should assist with reasoning and communication, but it should not directly control application state.

### Core Data Model

The backend should be organized around these core entities:

- `Conversation`
- `Message`
- `Patient`
- `Provider`
- `AvailabilitySlot`
- `Appointment`
- `Handoff`

These entities allow both chat and voice interactions to share a common source of truth.

### Workflow Principle

The primary workflow is appointment scheduling. The system should:

1. identify scheduling intent
2. collect missing patient information
3. map the patient’s requested body part or concern to the correct provider
4. present matching appointment slots
5. support refinements such as day-of-week constraints
6. confirm and book the appointment
7. continue the same conversation over phone when requested

### Safety Principle

Safety should not rely on prompting alone. The backend should enforce behavioral limits so the assistant does not provide medical advice or perform unsupported actions.

### Testing Principle

All business logic should remain backend-controlled and test-covered. Deterministic logic such as provider matching, slot filtering, workflow transitions, booking, and handoff behavior should be verifiable through tests.
