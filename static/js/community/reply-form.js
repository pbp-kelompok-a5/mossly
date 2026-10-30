export function initReplyForm() {
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-reply-form]");
    if (!form) return;

    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    const feedback = form.querySelector("[data-reply-feedback]");
    if (!button || button.disabled) return;

    button.disabled = true;
    if (feedback) feedback.textContent = "";

    try {
      const response = await fetch(
        form.getAttribute("action") || window.location.href,
        {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
        },
      );
      const data = await response.json();

      if (!response.ok) {
        const firstError = Object.values(data.errors || {})[0];
        throw new Error(
          firstError ? firstError[0].message : "Balasan tidak dapat dikirim.",
        );
      }

      const section = form.closest(".reply-section");
      const list = section.querySelector("[data-replies-list]");
      const empty = list.querySelector("[data-reply-empty]");
      if (empty) empty.remove();

      const reply = document.createElement("article");
      reply.className = "reply-card";
      reply.innerHTML = data.reply_html;
      list.append(reply);

      const count = section.querySelector("[data-reply-count]");
      if (count) count.textContent = data.reply_count;
      form.reset();
      if (feedback) feedback.textContent = data.message;
    } catch (error) {
      if (feedback) feedback.textContent = error.message;
      console.error("Tidak dapat mengirim balasan.", error);
    } finally {
      button.disabled = false;
    }
  });
}
