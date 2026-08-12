import { createBackendClient } from "./api/backendClient";
import { getApiBaseUrl, getDefaultUserId } from "./api/config";
import { AgentConsole } from "./components/AgentConsole";

const apiBaseUrl = getApiBaseUrl();
const api = createBackendClient({ baseUrl: apiBaseUrl });

export function App() {
  return <AgentConsole api={api} apiBaseUrl={apiBaseUrl} defaultUserId={getDefaultUserId()} />;
}
