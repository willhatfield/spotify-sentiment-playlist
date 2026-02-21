import {
  apiFetch,
  frontendUrl,
  checkAuth,
  logout,
} from "./config.js";

const connectedLabel = document.getElementById("connected-label");
const logoutBtn = document.getElementById("logout-btn");
const flowError = document.getElementById("flow-error");
const lastPrompt = document.getElementById("last-prompt");
const playlistBox = document.getElementById("playlist-box");
const playlistTitle = document.getElementById("playlist-title");
const playlistLink = document.getElementById("playlist-link");

const moodForm = document.getElementById("mood-form");
const moodInput = document.getElementById("mood-input");
const goalInput = document.getElementById("goal-input");
const charCount = document.getElementById("char-count");
const goalCharCount = document.getElementById("goal-char-count");
const createBtn = document.getElementById("create-btn");

const stagesInput = document.getElementById("stages-input");
const stagesValue = document.getElementById("stages-value");
const tracksInput = document.getElementById("tracks-input");
const tracksValue = document.getElementById("tracks-value");

let submitting = false;
let authState = { authenticated: false, displayName: null, userId: null };

function redirectToLogin() {
  window.location.replace(frontendUrl("login.html"));
}

function setHidden(el, hidden) {
  if (!el) {
    return;
  }
  el.classList.toggle("hidden", hidden);
}

function setError(target, message) {
  if (!target) {
    return;
  }

  if (!message) {
    target.textContent = "";
    target.classList.add("hidden");
    return;
  }

  target.textContent = message;
  target.classList.remove("hidden");
}

function detectMode(text) {
  const moodText = String(text || "").toLowerCase();
  if (/(sleep|insomnia|exhausted|tired|bed|night)/.test(moodText)) {
    return "sleep";
  }
  if (/(focus|study|deep work|concentrate|productive)/.test(moodText)) {
    return "focus";
  }
  if (/(workout|gym|lift|run|training)/.test(moodText)) {
    return "gym";
  }
  if (/(anxious|anxiety|stressed|stress|calm|panic)/.test(moodText)) {
    return "calm";
  }
  if (/(angry|rage|furious|mad|frustrated)/.test(moodText)) {
    return "rage_release";
  }
  return "uplift";
}

function setSubmitting(next) {
  submitting = next;
  if (createBtn) {
    createBtn.disabled = next;
    createBtn.textContent = next ? "Creating playlist..." : "Create MoodMix";
  }
}

function renderPlaylist(data) {
  if (!playlistTitle || !playlistLink) {
    return;
  }

  const playlistName = data?.playlist_name || data?.playlistName || "MoodMix Playlist";
  const playlistUrl = data?.playlist_url || data?.playlistUrl || "";

  playlistTitle.textContent = playlistName;

  if (playlistUrl) {
    playlistLink.href = playlistUrl;
    setHidden(playlistLink, false);
    setHidden(playlistBox, false);
  } else {
    const note = data?.spotify_note || "Playlist could not be created. Please try again.";
    setError(flowError, note);
  }
}

async function ensureAuthenticated() {
  setError(flowError, "");

  try {
    const backendAuth = await checkAuth();
    const spotifyUserId = backendAuth?.user_id || null;
    if (!backendAuth?.authenticated || !spotifyUserId) {
      redirectToLogin();
      return false;
    }

    authState = {
      authenticated: true,
      displayName: backendAuth.display_name || spotifyUserId,
      userId: spotifyUserId,
    };

    if (connectedLabel) {
      connectedLabel.textContent = `Connected as ${authState.displayName}`;
    }

    if (logoutBtn) {
      setHidden(logoutBtn, false);
    }

    return true;
  } catch (error) {
    setError(flowError, error.message || "Failed to load Spotify authentication status.");
    redirectToLogin();
    return false;
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  if (submitting || !moodInput || !goalInput) {
    return;
  }

  setError(flowError, "");
  const text = moodInput.value.trim();
  const goalText = goalInput.value.trim();

  if (!text) {
    setError(flowError, "Tell me how you are feeling right now.");
    return;
  }

  if (!goalText) {
    setError(flowError, "Tell me how you want to feel.");
    return;
  }

  if (!authState.authenticated) {
    setError(flowError, "Spotify session not available.");
    redirectToLogin();
    return;
  }

  setSubmitting(true);
  setHidden(playlistBox, true);

  try {
    const mode = detectMode(text + " " + goalText);
    const userStages = stagesInput ? parseInt(stagesInput.value, 10) : 5;
    const userTracks = tracksInput ? parseInt(tracksInput.value, 10) : 30;

    const playlistData = await apiFetch("/generate-mood-arc-playlist", {
      method: "POST",
      body: JSON.stringify({
        text,
        goal: goalText,
        mode,
        stages: userStages,
        tracks: userTracks,
        public: false,
      }),
    });

    renderPlaylist(playlistData);

    if (lastPrompt) {
      lastPrompt.textContent = `${text} → ${goalText}`;
      lastPrompt.classList.remove("hidden");
    }

    moodInput.value = "";
    goalInput.value = "";
    if (charCount) {
      charCount.textContent = "0/280";
    }
    if (goalCharCount) {
      goalCharCount.textContent = "0/280";
    }
  } catch (error) {
    setError(flowError, error.message || "Failed to create playlist.");
  } finally {
    setSubmitting(false);
  }
}

async function handleLogout() {
  if (logoutBtn) {
    logoutBtn.disabled = true;
  }

  try {
    await logout();
  } catch (error) {
    setError(flowError, error.message || "Could not sign out.");
  } finally {
    redirectToLogin();
  }
}

function bindEvents() {
  if (moodInput && charCount) {
    moodInput.addEventListener("input", () => {
      charCount.textContent = `${moodInput.value.length}/280`;
    });
  }

  if (goalInput && goalCharCount) {
    goalInput.addEventListener("input", () => {
      goalCharCount.textContent = `${goalInput.value.length}/280`;
    });
  }

  if (stagesInput && stagesValue) {
    stagesInput.addEventListener("input", () => {
      stagesValue.textContent = stagesInput.value;
    });
  }

  if (tracksInput && tracksValue) {
    tracksInput.addEventListener("input", () => {
      tracksValue.textContent = tracksInput.value;
    });
  }

  if (moodForm) {
    moodForm.addEventListener("submit", handleSubmit);
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }
}

async function bootstrap() {
  const authenticated = await ensureAuthenticated();
  if (!authenticated) {
    return;
  }

  bindEvents();
}

void bootstrap();
