const passwordInput = document.getElementById("password");
const passwordToggle = document.querySelector(".password-toggle");
const loginForm = document.getElementById("login-form");
const previewMessage = document.getElementById("preview-message");

passwordToggle.hidden = false;
passwordToggle.addEventListener("click", () => {
  const showPassword = passwordInput.type === "password";
  passwordInput.type = showPassword ? "text" : "password";
  passwordToggle.setAttribute("aria-pressed", String(showPassword));
  passwordToggle.setAttribute("aria-label", showPassword ? "Sembunyikan password" : "Tampilkan password");
});

// The first version previews the form without sending credentials.
loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  previewMessage.hidden = false;
});
