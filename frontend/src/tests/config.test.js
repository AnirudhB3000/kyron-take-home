import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "../lib/config";

describe("resolveApiBaseUrl", () => {
  it("uses the configured VITE_API_BASE_URL when provided", () => {
    expect(
      resolveApiBaseUrl({ VITE_API_BASE_URL: "https://kyron-api.onrender.com/api" }),
    ).toBe("https://kyron-api.onrender.com/api");
  });

  it("trims the configured VITE_API_BASE_URL", () => {
    expect(
      resolveApiBaseUrl({ VITE_API_BASE_URL: "  https://kyron-api.onrender.com/api  " }),
    ).toBe("https://kyron-api.onrender.com/api");
  });

  it("falls back to localhost when VITE_API_BASE_URL is missing", () => {
    expect(resolveApiBaseUrl({})).toBe("http://localhost:8000/api");
  });

  it("falls back to localhost when VITE_API_BASE_URL is blank", () => {
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: "   " })).toBe("http://localhost:8000/api");
  });
});
