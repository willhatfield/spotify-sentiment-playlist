export type EmotionScore = {
  label: string;
  score: number;
};

export type EmotionsResponse = {
  emotions: EmotionScore[];
  topEmotion: string;
};

export type AuthStatusResponse = {
  authenticated: boolean;
  displayName: string | null;
};

export type PlaylistTrack = {
  name: string;
  artist: string;
  uri: string;
};

export type CreatePlaylistRequest = {
  text: string;
  emotions: EmotionScore[];
  playlistName: string;
  isPublic: boolean;
};

export type CreatePlaylistResponse = {
  playlistId: string;
  playlistUrl: string;
  embedUrl: string;
  tracks: PlaylistTrack[];
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, "");

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function clampScore(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.min(1, Math.max(0, value));
}

async function getErrorMessageFromResponse(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as {
        detail?: string;
        message?: string;
      };
      return payload.detail ?? payload.message ?? `Request failed with status ${response.status}.`;
    } catch {
      return `Request failed with status ${response.status}.`;
    }
  }

  try {
    const text = await response.text();
    return text || `Request failed with status ${response.status}.`;
  } catch {
    return `Request failed with status ${response.status}.`;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  const hasBody = init.body !== undefined && init.body !== null;
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;

  if (hasBody && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw new ApiError(await getErrorMessageFromResponse(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
