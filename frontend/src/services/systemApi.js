import { API_BASE_URL } from "../lib/config";
import { createSystemStatus } from "../types/system";

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error("System information request failed");
  }

  return response.json();
}

async function post(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("System information request failed");
  }

  return response.json();
}

export async function fetchSystemStatus() {
  try {
    const payload = await request("/system/config-status");

    return createSystemStatus({
      label: payload.openai_configured ? "online" : "configuration needed",
      tone: payload.openai_configured ? "success" : "warning",
    });
  } catch {
    return createSystemStatus({
      label: "backend unavailable",
      tone: "danger",
    });
  }
}

export async function fetchOfficeHours() {
  return request("/system/office-hours");
}

export async function fetchOfficeAddress() {
  return request("/system/office-address");
}

export async function submitRefillRequest(message) {
  return post("/system/refill-request", { message });
}
