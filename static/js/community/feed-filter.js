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

export function initFeedFilter() {
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
}
