import { frontendUrl, redirectToBackendLogin, logout } from "./config.js";

const loginBtn = document.getElementById("login-btn");
const loginError = document.getElementById("login-error");

function setLoginError(message) {
  if (!loginError) {
    return;
  }

  if (!message) {
    loginError.textContent = "";
    loginError.classList.add("hidden");
    return;
  }

  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

function redirectTo(page) {
  window.location.replace(frontendUrl(page));
}

function bindLoginButton() {
  if (!loginBtn) {
    return;
  }

  loginBtn.addEventListener("click", async () => {
    setLoginError("");
    loginBtn.disabled = true;

    // Always clear prior backend session before starting OAuth.
    try {
      await logout();
    } catch {
      // Best-effort; continue to OAuth even if logout fails.
    }

    // Use backend OAuth flow (redirects to Spotify, then back to /auth/callback)
    try {
      redirectToBackendLogin();
    } catch (error) {
      setLoginError(error.message || "Could not start Spotify OAuth.");
      loginBtn.disabled = false;
    }
  });
}

function showLoginErrorFromQueryParam() {
  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const errorCode = searchParams.get("error") || hashParams.get("error");
  const errorDescription =
    searchParams.get("error_description") || hashParams.get("error_description") || searchParams.get("message");

  if (!errorCode) {
    return;
  }

  if (errorDescription) {
    setLoginError(errorDescription);
    return;
  }

  const spotifyStatus = searchParams.get("spotify_status");
  const statusHint = spotifyStatus ? ` [Spotify HTTP ${spotifyStatus}]` : "";
  setLoginError(`Spotify OAuth failed (${errorCode})${statusHint}. Please try again.`);
}

async function bootstrap() {
  showLoginErrorFromQueryParam();
  bindLoginButton();
}

void bootstrap();
