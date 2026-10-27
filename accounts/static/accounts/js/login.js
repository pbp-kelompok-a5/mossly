document.querySelectorAll(".password-toggle").forEach((passwordToggle) => {
  const passwordInput = document.getElementById(passwordToggle.getAttribute("aria-controls"));
  if (!passwordInput) return;
  passwordToggle.hidden = false;
  passwordToggle.addEventListener("click", () => {
    const showPassword = passwordInput.type === "password";
    passwordInput.type = showPassword ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(showPassword));
    passwordToggle.setAttribute("aria-label", showPassword ? "Sembunyikan password" : "Tampilkan password");
  });
});
