import type { UploadStatus } from "./types";

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

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
    throw new Error(body.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

export async function uploadPhoto(file: File, uploadType: string): Promise<UploadStatus> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${apiBaseUrl}/uploads/file?upload_type=${encodeURIComponent(uploadType)}`, {
    method: "POST",
    body,
  });
  return readJson<UploadStatus>(response);
}

export async function getUploadStatus(uploadId: string): Promise<UploadStatus> {
  const response = await fetch(`${apiBaseUrl}/uploads/${uploadId}`);
  return readJson<UploadStatus>(response);
}

export async function retryUpload(uploadId: string): Promise<UploadStatus> {
  const response = await fetch(`${apiBaseUrl}/uploads/${uploadId}/retry`, {
    method: "POST",
  });
  return readJson<UploadStatus>(response);
}

export async function deleteUpload(uploadId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/uploads/${uploadId}`, {
    method: "DELETE",
  });
  await readJson<{ id: string; status: string }>(response);
}
