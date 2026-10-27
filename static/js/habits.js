// Progressive enhancement for the Habit & Goal pages.
// Without JavaScript every trigger is a normal link to a full page, forms
// post normally, and the milestone dialog is rendered already open; this
// script only upgrades them.

document.documentElement.classList.add("js");

// --- Dialogs -------------------------------------------------------------------

// data-prefill-<field> on a trigger fills the dialog's field of that name,
// e.g. data-prefill-target-value sets name="target_value".
function prefillForm(dialog, trigger) {
  for (const [key, value] of Object.entries(trigger.dataset)) {
    if (!key.startsWith("prefill")) continue;
    const name = key
      .slice("prefill".length)
      .replace(/^./, (c) => c.toLowerCase())
      .replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
    dialog.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach((field) => {
      if (field.type === "radio") field.checked = field.value === value;
      else field.value = value;
      field.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }
}

function openDialog(event) {
  const trigger = event.target.closest("[data-dialog-open]");
  if (!trigger) return;
  const dialog = document.getElementById(trigger.dataset.dialogOpen);
  if (!dialog || typeof dialog.showModal !== "function") return;
  event.preventDefault();
  prefillForm(dialog, trigger);
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

// --- Log progress: stepper and "after saving" preview --------------------------

function formatAmount(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(".", ",");
}

function updateProgressPreview(form) {
  const preview = form.querySelector("[data-progress-preview]");
  const amount = parseFloat(form.querySelector('[name="amount"]').value) || 0;
  const target = parseFloat(form.dataset.target);
  const after = Math.round((parseFloat(form.dataset.progress) + amount) * 100) / 100;
  const percent = Math.min(100, Math.floor((after * 100) / target));
  preview.textContent =
    `Setelah disimpan: ${formatAmount(after)} / ${formatAmount(target)} ${form.dataset.unit} (${percent}%)`;
}

function stepAmount(event) {
  const button = event.target.closest("[data-step]");
  if (!button) return;
  const input = button.closest(".stepper").querySelector("input");
  const min = parseFloat(input.min) || 0;
  const next = (parseFloat(input.value) || 0) + Number(button.dataset.step);
  input.value = Math.round(Math.max(min, next) * 100) / 100;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

// --- Goal form: checklist rows and deadline hint -------------------------------

function updateChecklistCount(form) {
  const count = form.querySelector("[data-checklist-count]");
  if (!count) return;
  const filled = [...form.querySelectorAll('[name="checklist_label"]')].filter((input) => input.value.trim());
  count.textContent = `${filled.length} langkah`;
}

function editChecklist(event) {
  const add = event.target.closest("[data-checklist-add]");
  const remove = event.target.closest("[data-checklist-remove]");
  if (!add && !remove) return;
  const form = event.target.closest("form");
  const list = form.querySelector("[data-checklist-list]");
  if (add) {
    const row = list.lastElementChild.cloneNode(true);
    row.querySelectorAll("input").forEach((input) => { input.value = ""; });
    list.append(row);
    row.querySelector('[name="checklist_label"]').focus();
  } else {
    const row = remove.closest("li");
    if (list.children.length > 1) row.remove();
    else row.querySelectorAll("input").forEach((input) => { input.value = ""; });
  }
  updateChecklistCount(form);
}

function updateDeadlineHint(input) {
  const hint = input.closest(".field").querySelector("[data-deadline-hint]");
  if (!hint || !input.value) return;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((new Date(`${input.value}T00:00`) - today) / 86400000);
  hint.textContent = days > 0 ? `${days} hari dari sekarang` : days === 0 ? "Deadline hari ini" : "Tanggal ini sudah lewat";
}

// --- Wiring --------------------------------------------------------------------

document.addEventListener("click", openDialog);
document.addEventListener("click", closeOnBackdrop);
document.addEventListener("click", stepAmount);
document.addEventListener("click", editChecklist);

document.addEventListener("input", (event) => {
  const field = event.target;
  const progressForm = field.closest("[data-progress-form]");
  if (progressForm && field.name === "amount") updateProgressPreview(progressForm);
  if (field.matches("[data-deadline-input]")) updateDeadlineHint(field);
  if (field.name === "checklist_label") updateChecklistCount(field.closest("form"));
});

document.querySelectorAll("[data-deadline-input]").forEach(updateDeadlineHint);

document.querySelectorAll("dialog[data-autoshow]").forEach((dialog) => {
  if (typeof dialog.showModal !== "function") return;
  dialog.close();
  dialog.showModal();
});
