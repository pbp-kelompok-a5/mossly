function getLikeButton(form) {
  return form.querySelector("[data-like-button]");
}

function updateLikeButton(button, isLiked, count) {
  const state = button.querySelector("[data-like-state]");
  const countElement = button.querySelector("[data-like-count]");

  button.setAttribute("aria-pressed", String(isLiked));
  button.setAttribute(
    "aria-label",
    isLiked ? "Hapus apresiasi" : "Beri apresiasi",
  );
  if (state) state.textContent = isLiked ? "♥ Diapresiasi" : "♡ Beri apresiasi";
  if (countElement) countElement.textContent = count;
}

function restoreLikeButton(form) {
  const button = getLikeButton(form);
  if (!button || !form.dataset.likePreviousState) return;

  updateLikeButton(
    button,
    form.dataset.likePreviousState === "true",
    form.dataset.likePreviousCount,
  );
  button.disabled = false;
  form.classList.remove("is-pending", "is-liking", "is-unliking");
  delete form.dataset.likePreviousState;
  delete form.dataset.likePreviousCount;
}

export function initOptimisticLikes() {
  document.body.addEventListener("htmx:beforeRequest", (event) => {
    const form = event.detail.elt.closest("[data-like-control]");
    if (!form) return;

    const button = getLikeButton(form);
    const countElement = button?.querySelector("[data-like-count]");
    if (!button || !countElement || form.classList.contains("is-pending")) return;

    const wasLiked = button.getAttribute("aria-pressed") === "true";
    const previousCount = Number.parseInt(countElement.textContent, 10) || 0;
    const nextCount = Math.max(0, previousCount + (wasLiked ? -1 : 1));

    form.dataset.likePreviousState = String(wasLiked);
    form.dataset.likePreviousCount = String(previousCount);
    form.classList.add("is-pending", wasLiked ? "is-unliking" : "is-liking");
    button.disabled = true;
    updateLikeButton(button, !wasLiked, nextCount);
  });

  document.body.addEventListener("htmx:responseError", (event) => {
    const form = event.detail.elt.closest("[data-like-control]");
    if (form) restoreLikeButton(form);
  });

  document.body.addEventListener("htmx:sendError", (event) => {
    const form = event.detail.elt.closest("[data-like-control]");
    if (form) restoreLikeButton(form);
  });
}
