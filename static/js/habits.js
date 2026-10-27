// Progressive enhancement for the Habit & Goal pages.
// Without JavaScript every trigger is a normal link to a full page, and the
// milestone dialog is rendered already open; this script only upgrades them
// to native modal dialogs.

function prefillHabitForm(dialog, trigger) {
  const { prefillName, prefillIcon } = trigger.dataset;
  if (prefillName) {
    const input = dialog.querySelector('input[name="name"]');
    if (input) input.value = prefillName;
  }
  if (prefillIcon) {
    const radio = dialog.querySelector(`input[name="icon"][value="${CSS.escape(prefillIcon)}"]`);
    if (radio) radio.checked = true;
  }
}

function openDialog(event) {
  const trigger = event.target.closest("[data-dialog-open]");
  if (!trigger) return;
  const dialog = document.getElementById(trigger.dataset.dialogOpen);
  if (!dialog || typeof dialog.showModal !== "function") return;
  event.preventDefault();
  prefillHabitForm(dialog, trigger);
  dialog.showModal();
  dialog.querySelector("input:not([type=hidden]), button")?.focus();
}

// A click on the backdrop lands on the <dialog> itself, outside its box.
function closeOnBackdrop(event) {
  const dialog = event.target;
  if (!(dialog instanceof HTMLDialogElement) || !dialog.open) return;
  const box = dialog.getBoundingClientRect();
  const inside =
    event.clientX >= box.left && event.clientX <= box.right &&
    event.clientY >= box.top && event.clientY <= box.bottom;
  if (!inside) dialog.close();
}

document.addEventListener("click", openDialog);
document.addEventListener("click", closeOnBackdrop);

document.querySelectorAll("dialog[data-autoshow]").forEach((dialog) => {
  if (typeof dialog.showModal !== "function") return;
  dialog.close();
  dialog.showModal();
});
