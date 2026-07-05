// Mobile navigation drawer: hamburger toggle with slide-in menu.
// Progressive enhancement — without JS the drawer stays hidden and the
// standard header links (shown on desktop) remain the navigation.
(function () {
  const toggle = document.querySelector("[data-nav-toggle]");
  const drawer = document.querySelector("[data-nav-drawer]");
  const backdrop = document.querySelector("[data-nav-backdrop]");
  const closeBtn = document.querySelector("[data-nav-close]");
  if (!toggle || !drawer || !backdrop) return;

  let lastFocus = null;

  function open() {
    lastFocus = document.activeElement;
    drawer.classList.add("is-open");
    backdrop.hidden = false;
    // Force reflow so the backdrop transition runs from opacity 0.
    void backdrop.offsetWidth;
    backdrop.classList.add("is-open");
    document.body.classList.add("nav-open");
    toggle.setAttribute("aria-expanded", "true");
    drawer.setAttribute("aria-hidden", "false");
    const firstLink = drawer.querySelector("a, button, input");
    firstLink && firstLink.focus();
  }

  function close() {
    drawer.classList.remove("is-open");
    backdrop.classList.remove("is-open");
    document.body.classList.remove("nav-open");
    toggle.setAttribute("aria-expanded", "false");
    drawer.setAttribute("aria-hidden", "true");
    // Hide backdrop after its fade-out transition.
    setTimeout(() => { backdrop.hidden = true; }, 250);
    lastFocus && lastFocus.focus();
  }

  toggle.addEventListener("click", open);
  closeBtn && closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", close);

  // Close after tapping any navigation link.
  drawer.querySelectorAll(".drawer-nav a, .drawer-account a").forEach((a) => {
    a.addEventListener("click", close);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && drawer.classList.contains("is-open")) close();
  });
})();
