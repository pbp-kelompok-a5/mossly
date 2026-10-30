const interactiveSelector = "a, button, form, input, textarea, select, label";

export function initCardNavigation() {
  document.addEventListener("click", (event) => {
    const card = event.target.closest("[data-thread-url]");
    if (!card || event.target.closest(interactiveSelector)) return;

    window.location.href = card.dataset.threadUrl;
  });

  document.addEventListener("keydown", (event) => {
    const card = event.target.closest("[data-thread-url]");
    if (!card || (event.key !== "Enter" && event.key !== " ")) return;

    event.preventDefault();
    window.location.href = card.dataset.threadUrl;
  });
}
