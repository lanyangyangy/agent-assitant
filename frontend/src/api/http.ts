type FetchLike = typeof fetch;

export interface RequestOptions extends RequestInit {
  userId?: string;
}

export async function requestJson<T>(
  baseUrl: string,
  path: string,
  options: RequestOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<T> {
  const { userId, headers: inputHeaders, ...fetchOptions } = options;
  const headers = normalizeHeaders(inputHeaders);
  if (userId) {
    headers["X-User-Id"] = userId;
  }
  if (fetchOptions.body && !hasHeader(headers, "Content-Type")) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, { ...fetchOptions, headers });
  } catch {
    throw new Error("无法连接后端，请确认服务已启动。");
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `请求失败，状态码 ${response.status}。`);
  }

  return response.json() as Promise<T>;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return typeof payload.detail === "string" ? payload.detail : "";
  } catch {
    return "";
  }
}

function normalizeHeaders(input: HeadersInit | undefined): Record<string, string> {
  if (!input) {
    return {};
  }
  if (input instanceof Headers) {
    return Object.fromEntries(input.entries());
  }
  if (Array.isArray(input)) {
    return Object.fromEntries(input);
  }
  return { ...input };
}

function hasHeader(headers: Record<string, string>, name: string): boolean {
  return Object.keys(headers).some((key) => key.toLowerCase() === name.toLowerCase());
}
