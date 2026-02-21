import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const runtimeConfig = window.__MOODMIX_CONFIG__ || {};

function readMetaContent(name) {
  return document.querySelector(`meta[name="${name}"]`)?.getAttribute("content")?.trim() || "";
}

const metaApiBase = readMetaContent("api-base-url");
const metaSupabaseUrl = readMetaContent("supabase-url");
const metaSupabaseAnonKey = readMetaContent("supabase-anon-key");
const metaProfilesTable = readMetaContent("supabase-profiles-table");
const metaMoodHistoryTable = readMetaContent("supabase-mood-history-table");

const rawApiBase = runtimeConfig.apiBaseUrl || metaApiBase || window.location.origin;

function normalizeBasePath(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return "";
  }

  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

function inferFrontendBasePathFromLocation() {
  const pathname = window.location.pathname || "/";
  const lastSlashIndex = pathname.lastIndexOf("/");

  if (lastSlashIndex <= 0) {
    return "";
  }

  return pathname.slice(0, lastSlashIndex);
}

function parseErrorMessage(payload, statusCode) {
  if (!payload) {
    return `Request failed (${statusCode}).`;
  }

  if (typeof payload === "string") {
    return payload;
  }

  if (typeof payload === "object") {
    return payload.detail || payload.message || `Request failed (${statusCode}).`;
  }

  return `Request failed (${statusCode}).`;
}

function asErrorMessage(error, fallback) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

function isIgnorableSupabaseDbError(error) {
  const message = String(error?.message || "").toLowerCase();
  return (
    error?.code === "PGRST116" ||
    error?.code === "PGRST205" ||
    error?.code === "42P01" ||
    message.includes("does not exist") ||
    message.includes("relation") ||
    message.includes("schema cache")
  );
}

function isLocalHostname(hostname) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function isApiBaseLocalhost(apiBaseUrl) {
  try {
    const parsed = new URL(apiBaseUrl);
    return isLocalHostname(parsed.hostname);
  } catch {
    return false;
  }
}

function ensureApiReachableFromFrontend() {
  if (!API_BASE_URL) {
    return;
  }

  const frontendIsLocal = isLocalHostname(window.location.hostname);
  if (!frontendIsLocal && isApiBaseLocalhost(API_BASE_URL)) {
    throw new Error(
      "API base URL points to localhost, which is unreachable from this hosted frontend. Set NEXT_PUBLIC_API_BASE_URL to a public HTTPS URL (for example, a tunnel URL)."
    );
  }
}

const rawFrontendBase = runtimeConfig.frontendBasePath || inferFrontendBasePathFromLocation();

export const API_BASE_URL = String(rawApiBase || "").replace(/\/+$/, "");
export const FRONTEND_BASE_PATH = normalizeBasePath(rawFrontendBase);

export const SUPABASE_URL = String(runtimeConfig.supabaseUrl || metaSupabaseUrl || "").trim();
export const SUPABASE_ANON_KEY = String(runtimeConfig.supabaseAnonKey || metaSupabaseAnonKey || "").trim();
export const SUPABASE_CONFIGURED = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
export const SUPABASE_TABLES = {
  profiles: runtimeConfig.supabaseProfilesTable || metaProfilesTable || "profiles",
  moodHistory: runtimeConfig.supabaseMoodHistoryTable || metaMoodHistoryTable || "mood_history",
};

export const supabase = SUPABASE_CONFIGURED
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    })
  : null;

export function isSupabaseConfigured() {
  return SUPABASE_CONFIGURED;
}

export function getSupabaseClient() {
  if (!supabase) {
    throw new Error(
      "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env, then regenerate frontend/runtime-config.js."
    );
  }

  return supabase;
}

export function frontendUrl(page) {
  const normalizedPage = String(page || "").replace(/^\/+/, "");
  return FRONTEND_BASE_PATH ? `${FRONTEND_BASE_PATH}/${normalizedPage}` : `/${normalizedPage}`;
}

export function apiUrl(path) {
  const normalizedPath = String(path || "").startsWith("/") ? String(path || "") : `/${String(path || "")}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function getCookie(name) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

export async function getSupabaseSession() {
  if (!supabase) {
    return null;
  }

  const { data, error } = await supabase.auth.getSession();
  if (error) {
    throw new Error(asErrorMessage(error, "Failed to fetch Supabase session."));
  }

  return data.session || null;
}

export async function getSupabaseUser() {
  if (!supabase) {
    return null;
  }

  const { data, error } = await supabase.auth.getUser();
  if (error) {
    throw new Error(asErrorMessage(error, "Failed to fetch Supabase user."));
  }

  return data.user || null;
}

export async function signInWithSpotify({ redirectPage = "webapp.html" } = {}) {
  const client = getSupabaseClient();
  const redirectTo = new URL(frontendUrl(redirectPage), window.location.origin).toString();
  const queryParams = {};

  if (runtimeConfig.spotifyShowDialog === true || runtimeConfig.spotifyShowDialog === false) {
    queryParams.show_dialog = String(Boolean(runtimeConfig.spotifyShowDialog));
  }

  const { data, error } = await client.auth.signInWithOAuth({
    provider: "spotify",
    options: {
      redirectTo,
      queryParams,
    },
  });

  if (error) {
    throw new Error(asErrorMessage(error, "Could not start Spotify OAuth."));
  }

  return data;
}

export async function signOutFromSupabase() {
  if (!supabase) {
    return;
  }

  const { error } = await supabase.auth.signOut();
  if (error) {
    throw new Error(asErrorMessage(error, "Could not sign out."));
  }
}

// ============ Backend Session Auth Functions ============

export async function checkAuth() {
  try {
    const response = await fetch(apiUrl("/auth/me"), {
      credentials: "include",
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch {
    return null;
  }
}

export async function logout() {
  try {
    await fetch(apiUrl("/auth/logout"), {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Ignore errors during logout
  }
}

export function redirectToBackendLogin() {
  window.location.href = apiUrl("/auth/login");
}

export async function upsertUserProfile(profile = {}) {
  if (!supabase) {
    return;
  }

  const user = await getSupabaseUser();
  if (!user) {
    return;
  }

  const payload = {
    id: user.id,
    email: user.email || null,
    display_name: profile.displayName || user.user_metadata?.full_name || user.user_metadata?.name || null,
    avatar_url: profile.avatarUrl || user.user_metadata?.avatar_url || null,
    spotify_handle:
      profile.spotifyHandle || user.user_metadata?.preferred_username || user.user_metadata?.user_name || null,
    updated_at: new Date().toISOString(),
  };

  const { error } = await supabase.from(SUPABASE_TABLES.profiles).upsert(payload, {
    onConflict: "id",
  });

  if (error && !isIgnorableSupabaseDbError(error)) {
    throw new Error(asErrorMessage(error, "Could not save profile."));
  }
}

export async function insertMoodHistory(row = {}) {
  if (!supabase) {
    return;
  }

  const user = await getSupabaseUser();
  if (!user) {
    return;
  }

  const payload = {
    user_id: user.id,
    prompt: row.prompt || null,
    top_emotion: row.topEmotion || null,
    playlist_name: row.playlistName || null,
    playlist_url: row.playlistUrl || null,
    created_at: new Date().toISOString(),
  };

  const { error } = await supabase.from(SUPABASE_TABLES.moodHistory).insert(payload);

  if (error && !isIgnorableSupabaseDbError(error)) {
    throw new Error(asErrorMessage(error, "Could not save mood history."));
  }
}

export async function apiFetch(path, init = {}) {
  ensureApiReachableFromFrontend();

  const headers = new Headers(init.headers || {});
  const hasBody = init.body !== undefined && init.body !== null;
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;

  if (hasBody && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let accessToken = "";
  try {
    const session = await getSupabaseSession();
    accessToken = session?.access_token || "";
  } catch {
    accessToken = "";
  }

  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") || "";
  let payload = null;

  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  } else {
    const text = await response.text();
    payload = text ? { message: text } : null;
  }

  if (!response.ok) {
    throw new Error(parseErrorMessage(payload, response.status));
  }

  return payload;
}
