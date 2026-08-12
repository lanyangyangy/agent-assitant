export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || "/api";
}

export function getDefaultUserId(): string {
  if (import.meta.env.VITE_DEFAULT_USER_ID) {
    return import.meta.env.VITE_DEFAULT_USER_ID;
  }

  const storageKey = "agent-console-user-id";
  const storedUserId = localStorage.getItem(storageKey);
  if (storedUserId) {
    return storedUserId;
  }

  const generatedUserId = `local-user-${crypto.randomUUID().slice(0, 8)}`;
  localStorage.setItem(storageKey, generatedUserId);
  return generatedUserId;
}
