import type { GarmentCard, UploadStatus } from "./types";

type ImportMetaWithEnv = ImportMeta & {
  env?: {
    VITE_API_URL?: string;
  };
};

function defaultApiUrl(): string {
  const explicitUrl = (import.meta as ImportMetaWithEnv).env?.VITE_API_URL;
  if (explicitUrl) {
    return explicitUrl.replace(/\/$/, "");
  }
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return "http://localhost:8010";
  }
  return window.location.origin;
}

export const apiBaseUrl = defaultApiUrl();

type TokenPair = {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
};

type ApiGarmentItem = {
  id: string;
  title: string;
  category: string;
  season: string[];
  main_color?: string | null;
  confidence: string | number;
  status: string;
  availability_status: string;
  designer_attributes: Record<string, unknown>;
};

const accessTokenKey = "aiw_access_token";
const refreshTokenKey = "aiw_refresh_token";

function saveTokens(tokens: TokenPair): void {
  window.localStorage.setItem(accessTokenKey, tokens.access_token);
  if (tokens.refresh_token) {
    window.localStorage.setItem(refreshTokenKey, tokens.refresh_token);
  }
}

export function hasAccessToken(): boolean {
  return Boolean(window.localStorage.getItem(accessTokenKey));
}

export async function authenticateWithTelegram(initData: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/auth/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  saveTokens(await readJson<TokenPair>(response));
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = window.localStorage.getItem(refreshTokenKey);
  if (!refreshToken) {
    return false;
  }
  const response = await fetch(`${apiBaseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    window.localStorage.removeItem(accessTokenKey);
    window.localStorage.removeItem(refreshTokenKey);
    return false;
  }
  saveTokens(await response.json());
  return true;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
    throw new Error(body.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}, retried = false): Promise<Response> {
  const token = window.localStorage.getItem(accessTokenKey);
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && !retried && (await refreshAccessToken())) {
    return authenticatedFetch(input, init, true);
  }
  return response;
}

export async function uploadPhoto(file: File, uploadType: string): Promise<UploadStatus> {
  const body = new FormData();
  body.append("file", file);
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/file?upload_type=${encodeURIComponent(uploadType)}`, {
    method: "POST",
    body,
  });
  return readJson<UploadStatus>(response);
}

export async function getUploadStatus(uploadId: string): Promise<UploadStatus> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}`);
  return readJson<UploadStatus>(response);
}

export async function retryUpload(uploadId: string): Promise<UploadStatus> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}/retry`, {
    method: "POST",
  });
  return readJson<UploadStatus>(response);
}

export async function deleteUpload(uploadId: string): Promise<void> {
  const response = await authenticatedFetch(`${apiBaseUrl}/uploads/${uploadId}`, {
    method: "DELETE",
  });
  await readJson<{ id: string; status: string }>(response);
}

export async function listWardrobeItems(): Promise<GarmentCard[]> {
  const response = await authenticatedFetch(`${apiBaseUrl}/items`);
  const items = await readJson<ApiGarmentItem[]>(response);
  return items.map((item) => ({
    title: item.title,
    imageClass: "swatch neutral",
    season: item.season.join(" · ") || "all season",
    role: item.category,
    temperature: item.availability_status,
    confidence: Number(item.confidence),
    provenance: "user_processed",
  }));
}
