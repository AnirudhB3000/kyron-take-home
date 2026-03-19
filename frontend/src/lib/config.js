const DEFAULT_API_BASE_URL = "http://localhost:8000/api";

export function resolveApiBaseUrl(env = import.meta.env) {
  const configuredBaseUrl = env?.VITE_API_BASE_URL?.trim();
  return configuredBaseUrl || DEFAULT_API_BASE_URL;
}

export const API_BASE_URL = resolveApiBaseUrl();
