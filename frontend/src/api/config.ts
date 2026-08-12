export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || "/api";
}

export function getDefaultUserId(): string {
  return import.meta.env.VITE_DEFAULT_USER_ID || "alice";
}
