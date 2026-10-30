// Landing page: apples drop when the user scrolls down to them. The fall itself
// is a Tailwind animation switched on by data-falling (see landing.html).

const apples = [...document.querySelectorAll("[data-apple]")];
let lastY = window.scrollY;

function updateApples() {
  const y = window.scrollY;
  const scrollingDown = y > lastY;
  lastY = y;

  apples.forEach((apple) => {
    const section = apple.closest("section").getBoundingClientRect();
    const offScreen = section.bottom <= 0 || section.top >= window.innerHeight;
    if (offScreen || y <= 0) {
      apple.removeAttribute("data-falling"); // back on the tree, ready to fall again
    } else if (scrollingDown && section.top < window.innerHeight * 0.5) {
      apple.setAttribute("data-falling", "");
    }
  });
}

window.addEventListener("scroll", updateApples, { passive: true });

// --- Reveal on scroll -----------------------------------------------------------

// Only this script hides anything: without it, without Tailwind, or with reduced
// motion, all content simply stays visible. Blocks already on screen at load stay put.
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.dataset.reveal = "shown";
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -10% 0px" });

  document.querySelectorAll("[data-reveal]").forEach((block) => {
    if (block.getBoundingClientRect().top < window.innerHeight) return;
    block.dataset.reveal = "hidden";
    observer.observe(block);
  });
}
