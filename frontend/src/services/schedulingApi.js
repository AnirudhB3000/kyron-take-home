import { API_BASE_URL } from "../lib/config";
import {
  createBookingResponse,
  createProviderMatchResponse,
  createSchedulingConversationResponse,
  createSlotListResponse,
  createTurnResponse,
} from "../types/scheduling";
import { createHandoffResponse } from "../types/handoff";

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error("Unable to reach the scheduling service right now.");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed.");
  }

  return response.json();
}

export async function createConversation() {
  const payload = await request("/scheduling/conversations", { method: "POST" });
  return createSchedulingConversationResponse(payload);
}

export async function processTurn(conversationId, message) {
  const payload = await request(`/scheduling/conversations/${conversationId}/turn`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return createTurnResponse(payload);
}

export async function updateIntake(conversationId, intake) {
  const payload = await request(`/scheduling/conversations/${conversationId}/intake`, {
    method: "PATCH",
    body: JSON.stringify(intake),
  });
  return createSchedulingConversationResponse(payload);
}

export async function extractIntake(conversationId, message) {
  const payload = await request(`/scheduling/conversations/${conversationId}/intake-extract`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return createSchedulingConversationResponse(payload);
}

export async function matchProvider(conversationId) {
  const payload = await request(
    `/scheduling/conversations/${conversationId}/provider-match`,
    { method: "POST" },
  );
  return createProviderMatchResponse(payload);
}

export async function listSlots(conversationId, weekday) {
  const search = weekday ? `?weekday=${encodeURIComponent(weekday)}` : "";
  const payload = await request(
    `/scheduling/conversations/${conversationId}/slots${search}`,
  );
  return createSlotListResponse(payload);
}

export async function bookAppointment(conversationId, slotId) {
  const payload = await request(`/scheduling/conversations/${conversationId}/book`, {
    method: "POST",
    body: JSON.stringify({ slot_id: slotId }),
  });
  return createBookingResponse(payload);
}

export async function startVoiceHandoff(conversationId) {
  const payload = await request(`/scheduling/conversations/${conversationId}/handoff`, {
    method: "POST",
  });
  return createHandoffResponse(payload);
}
