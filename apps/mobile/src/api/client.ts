import Constants from "expo-constants";

import { useAuth } from "@/state/auth";

const baseUrl =
  process.env.EXPO_PUBLIC_API_URL ??
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const token = useAuth.getState().devUserId;

  const resp = await fetch(`${baseUrl}/api/v1${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Dev-User-Id": token } : {}),
      ...(headers ?? {}),
    },
    body: json !== undefined ? JSON.stringify(json) : (rest.body as BodyInit | null | undefined),
  });

  const contentType = resp.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await resp.json().catch(() => null) : await resp.text();

  if (!resp.ok) {
    const message = (isJson && (body as { detail?: string } | null)?.detail) || resp.statusText;
    throw new ApiError(resp.status, message, body);
  }
  return body as T;
}
