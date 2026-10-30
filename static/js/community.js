(() => {
  const interactiveSelector = "a, button, form, input, textarea, select, label";

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

  async function updateThreadFeed(url) {
    const feed = document.querySelector("[data-thread-feed]");
    if (!feed) return;

    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    if (!response.ok) throw new Error(`Filter request failed (${response.status})`);

    const data = await response.json();
    feed.innerHTML = data.thread_html;
    if (window.htmx) window.htmx.process(feed);
    document.querySelectorAll("[data-category-filter]").forEach((filter) => {
      const filterUrl = new URL(filter.href);
      const filterCategory = filterUrl.searchParams.get("category") || "";
      const isSelected = filterCategory === data.category;

      filter.classList.toggle("selected", isSelected);
      if (isSelected) {
        filter.setAttribute("aria-current", "page");
      } else {
        filter.removeAttribute("aria-current");
      }
    });
    window.history.pushState({}, "", url);
  }

  document.addEventListener("click", async (event) => {
    const link = event.target.closest(
      "[data-category-filter], [data-thread-feed] .pagination a",
    );
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    event.preventDefault();
    link.setAttribute("aria-busy", "true");
    try {
      await updateThreadFeed(link.href);
    } catch (error) {
      console.error("Tidak dapat memperbarui daftar cerita.", error);
      window.location.assign(link.href);
    } finally {
      link.removeAttribute("aria-busy");
    }
  });
})();
