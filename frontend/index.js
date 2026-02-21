import { frontendUrl } from "./config.js";

const bootMessage = document.getElementById("boot-message");

function setBootMessage(message) {
  if (bootMessage) {
    bootMessage.textContent = message;
  }
}

function redirectTo(page) {
  window.location.replace(frontendUrl(page));
}

function bootstrap() {
  setBootMessage("Redirecting to Spotify sign-in...");
  redirectTo("login.html");
}

void bootstrap();
