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

// --- Habit groups: remember which time-of-day groups are folded ---------------

const FOLDED_GROUPS_KEY = "habits.foldedGroups";

// Storage can be blocked (private mode); the groups then just start open.
function readFoldedGroups() {
  try {
    return new Set(JSON.parse(localStorage.getItem(FOLDED_GROUPS_KEY)) || []);
  } catch {
    return new Set();
  }
}

function rememberGroup(key, opening) {
  const folded = readFoldedGroups();
  if (opening) folded.delete(key);
  else folded.add(key);
  try {
    localStorage.setItem(FOLDED_GROUPS_KEY, JSON.stringify([...folded]));
  } catch {
    // Not saved; the group still folds for this visit.
  }
}

// --- Goal card checklists: folded by default, remember the open ones ----------

// Ticking a step reloads the page; without this the checklist would fold again.
const OPEN_CHECKLISTS_KEY = "habits.openChecklists";

function readOpenChecklists() {
  try {
    return new Set(JSON.parse(localStorage.getItem(OPEN_CHECKLISTS_KEY)) || []);
  } catch {
    return new Set();
  }
}

function rememberChecklist(key, opening) {
  const open = readOpenChecklists();
  if (opening) open.add(key);
  else open.delete(key);
  try {
    localStorage.setItem(OPEN_CHECKLISTS_KEY, JSON.stringify([...open]));
  } catch {
    // Not saved; it just folds again after the next reload.
  }
}

// --- Scroll boxes: show N rows, scroll the rest --------------------------------

// data-max-rows="6" caps the box at the bottom of its sixth <li>, so day labels
// between rows never cut a row in half.
function limitRows(box) {
  const rows = box.querySelectorAll("li");
  const max = Number(box.dataset.maxRows);
  box.style.maxHeight = "";
  if (rows.length <= max) return;
  const style = getComputedStyle(box);
  const bottom = rows[max - 1].getBoundingClientRect().bottom - box.getBoundingClientRect().top + box.scrollTop;
  box.style.maxHeight = `${bottom + parseFloat(style.paddingBottom) + parseFloat(style.borderBottomWidth)}px`;
}

// --- Wiring --------------------------------------------------------------------

document.addEventListener("click", openDialog);
document.addEventListener("click", closeOnBackdrop);
document.addEventListener("click", (event) => {
  event.target.closest("[data-dialog-close]")?.closest("dialog")?.close();
});
document.addEventListener("click", stepAmount);
document.addEventListener("click", editChecklist);

document.addEventListener("input", (event) => {
  const field = event.target;
  const progressForm = field.closest("[data-progress-form]");
  if (progressForm && field.name === "amount") updateProgressPreview(progressForm);
  if (field.matches("[data-deadline-input]")) updateDeadlineHint(field);
  if (field.name === "checklist_label") updateChecklistCount(field.closest("form"));
});

// Clicks, not "toggle": a <details open> swapped in by htmx also fires toggle, which
// would read as the user reopening a folded group. Keyboard use arrives as a click too.
document.addEventListener("click", (event) => {
  const details = event.target.closest("summary")?.parentElement;
  if (!details) return;
  if (details.dataset.group) rememberGroup(details.dataset.group, !details.open);
  if (details.dataset.openKey) rememberChecklist(details.dataset.openKey, !details.open);
});

// Rows rewrap at other widths, so the height is measured again.
window.addEventListener("resize", () => {
  document.querySelectorAll("[data-max-rows]").forEach(limitRows);
});

// Runs on load and right after each htmx swap. afterSwap, not afterSettle: it runs before
// the browser paints, so restored checklists and folded groups never show in the wrong state.
function setUpPage() {
  document.querySelectorAll("[data-deadline-input]").forEach(updateDeadlineHint);
  document.querySelectorAll("[data-max-rows]").forEach(limitRows);

  const openChecklists = readOpenChecklists();
  document.querySelectorAll("details[data-open-key]").forEach((details) => {
    if (openChecklists.has(details.dataset.openKey)) details.open = true;
  });

  const foldedGroups = readFoldedGroups();
  document.querySelectorAll("details[data-group]").forEach((group) => {
    if (foldedGroups.has(group.dataset.group)) group.open = false;
  });

  document.querySelectorAll("dialog[data-autoshow]").forEach((dialog) => {
    if (typeof dialog.showModal !== "function") return;
    dialog.close();
    dialog.showModal();
  });
}

setUpPage();
document.addEventListener("htmx:afterSwap", setUpPage);
// A form that came back with errors stays in its dialog: bring the first one into view.
document.addEventListener("htmx:afterSettle", (event) => {
  if (!event.target.closest("dialog")) return;
  event.target.querySelector(".field-error, .alert-error")?.scrollIntoView({ block: "center" });
});
