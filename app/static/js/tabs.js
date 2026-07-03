// Show-page tool tabs (Calculator | Planner). Toggles the active tab button
// and its matching panel. Panels are all in the DOM so their widgets (and the
// server-driven calc/plan scripts) initialize regardless of which is visible.
(function () {
  document.querySelectorAll(".show-tools .tabs").forEach(function (tabsEl) {
    const root = tabsEl.closest(".show-tools");
    const tabs = Array.from(tabsEl.querySelectorAll(".tab"));
    const panels = Array.from(root.querySelectorAll(".tab-panel"));

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        const name = tab.dataset.tab;
        tabs.forEach(function (t) {
          const on = t === tab;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        panels.forEach(function (p) {
          p.classList.toggle("is-hidden", p.dataset.panel !== name);
        });
      });
    });
  });
})();
