const metaApiBase = document
  .querySelector('meta[name="api-base-url"]')
  ?.getAttribute("content")
  ?.trim();

const API_BASE_URL = (window.API_BASE_URL || metaApiBase || "http://localhost:8000").replace(/\/+$/, "");

const statusCard = document.getElementById("status-card");
const statusText = document.getElementById("status-text");
const statusSpinner = document.getElementById("status-spinner");

const loginView = document.getElementById("login-view");
const loginBtn = document.getElementById("login-btn");
const loginError = document.getElementById("login-error");

const appView = document.getElementById("app-view");
const connectedLabel = document.getElementById("connected-label");
const flowError = document.getElementById("flow-error");
const lastPrompt = document.getElementById("last-prompt");
const playlistBox = document.getElementById("playlist-box");
const playlistTitle = document.getElementById("playlist-title");
const topEmotionText = document.getElementById("top-emotion");
const playlistLink = document.getElementById("playlist-link");
const tracksList = document.getElementById("tracks-list");

const moodForm = document.getElementById("mood-form");
const moodInput = document.getElementById("mood-input");
const charCount = document.getElementById("char-count");
const createBtn = document.getElementById("create-btn");

let submitting = false;
let authState = { authenticated: false, displayName: null };

function capitalize(value) {
  if (!value) return "Unknown";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function clampScore(score) {
  if (!Number.isFinite(score)) return 0;
  if (score < 0) return 0;
  if (score > 1) return 1;
  return score;
}

function normalizeEmotions(items) {
  return (items || []).map((emotion) => ({
    label: emotion.label,
    score: clampScore(Number(emotion.score)),
  }));
}

function setHidden(el, hidden) {
  if (!el) return;
  el.classList.toggle("hidden", hidden);
}

function setError(target, message) {
  if (!target) return;
  if (message) {
    target.textContent = message;
    target.classList.remove("hidden");
    return;
  }
  target.textContent = "";
  target.classList.add("hidden");
}

async function apiFetch(path, init = {}) {
  const headers = new Headers(init.headers || {});
  const hasBody = init.body !== undefined && init.body !== null;

  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const response = await fetch(`${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`, {
    ...init,
    headers,
    credentials: "include",
  });

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    const text = await response.text();
    payload = text ? { message: text } : null;
  }

  if (!response.ok) {
    const message =
      payload?.detail || payload?.message || `Request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }

  return payload;
}

function renderAuthenticatedView() {
  statusCard.classList.add("hidden");
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  connectedLabel.innerHTML = `Connected as <strong>${authState.displayName || "Spotify user"}</strong>`;
}

function renderLoginView() {
  statusCard.classList.add("hidden");
  appView.classList.add("hidden");
  loginView.classList.remove("hidden");
}

async function checkAuth() {
  statusText.textContent = "Checking Spotify session...";
  statusSpinner.classList.remove("hidden");
  setHidden(statusCard, false);
  setError(loginError, "");
  setError(flowError, "");

  try {
    const status = await apiFetch("/auth/spotify/status", {
      method: "GET",
      cache: "no-store",
    });
    authState = {
      authenticated: Boolean(status?.authenticated),
      displayName: status?.displayName || null,
    };

    if (authState.authenticated) {
      renderAuthenticatedView();
    } else {
      renderLoginView();
    }
  } catch (error) {
    renderLoginView();
    setError(loginError, error.message || "Failed to load Spotify auth status.");
  } finally {
    statusSpinner.classList.add("hidden");
  }
}

function setSubmitting(next) {
  submitting = next;
  createBtn.disabled = next;
  createBtn.textContent = next ? "Creating playlist..." : "Create MoodMix";
}

function renderPlaylist(data) {
  playlistTitle.textContent = data.playlistName;
  topEmotionText.textContent = `Top mood detected: ${capitalize(data.topEmotion)}`;
  playlistLink.href = data.playlistUrl;
  tracksList.innerHTML = "";

  const tracks = (data.tracks || []).slice(0, 10);
  if (tracks.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No tracks returned.";
    tracksList.appendChild(li);
  } else {
    tracks.forEach((track, index) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${index + 1}. ${track.name}</strong> <span class="muted">by ${track.artist}</span>`;
      tracksList.appendChild(li);
    });
  }

  setHidden(playlistBox, false);
}

async function handleSubmit(event) {
  event.preventDefault();
  if (submitting) return;

  setError(flowError, "");
  const text = moodInput.value.trim();

  if (!text) {
    setError(flowError, "Tell me how you are feeling first.");
    return;
  }

  if (!authState.authenticated) {
    setError(flowError, "Login with Spotify to continue.");
    renderLoginView();
    return;
  }

  setSubmitting(true);
  setHidden(playlistBox, true);

  try {
    const emotionData = await apiFetch("/emotions", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    const emotions = normalizeEmotions(emotionData?.emotions);
    const topEmotion =
      emotionData?.topEmotion ||
      [...emotions].sort((a, b) => b.score - a.score)[0]?.label ||
      "mood";
    const playlistName = `MoodMix: ${capitalize(topEmotion)}`;

    const playlistData = await apiFetch("/spotify/create-playlist", {
      method: "POST",
      body: JSON.stringify({
        text,
        emotions,
        playlistName,
        isPublic: false,
      }),
    });

    renderPlaylist({
      ...playlistData,
      playlistName,
      topEmotion,
    });
    lastPrompt.textContent = text;
    lastPrompt.classList.remove("hidden");
    moodInput.value = "";
    charCount.textContent = "0/280";
  } catch (error) {
    setError(flowError, error.message || "Failed to create playlist.");
  } finally {
    setSubmitting(false);
  }
}

loginBtn.addEventListener("click", () => {
  window.location.assign(`${API_BASE_URL}/auth/spotify/login`);
});

moodInput.addEventListener("input", () => {
  charCount.textContent = `${moodInput.value.length}/280`;
});

moodForm.addEventListener("submit", handleSubmit);

checkAuth();
