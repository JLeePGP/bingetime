// Binge planner UI. Math + .ics both come from the server.
(function () {
  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, arguments), ms);
    };
  }

  const root = document.querySelector(".planner");
  if (!root) return;

  const fixedBase = parseInt(root.dataset.baseMin || "0", 10);
  const title = root.dataset.showTitle || "your show";
  const baseInput = root.querySelector('[name="total_runtime_min"]');
  const hoursInput = root.querySelector('[name="hours_per_week"]');
  const results = root.querySelector(".planner-results");
  const icsLink = root.querySelector("[data-ics]");
  const out = (k) => root.querySelector(`[data-out="${k}"]`);

  async function recalc() {
    const base = baseInput ? parseInt(baseInput.value || "0", 10) : fixedBase;
    const hpw = parseFloat((hoursInput && hoursInput.value) || "0");
    if (!base || base <= 0 || !hpw || hpw <= 0) {
      if (results) results.hidden = true;
      return;
    }
    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total_runtime_min: base, hours_per_week: hpw }),
      });
      if (!res.ok) return;
      const d = await res.json();
      out("finish_date").textContent = new Date(d.finish_date + "T00:00:00").toLocaleDateString(
        undefined,
        { weekday: "long", year: "numeric", month: "long", day: "numeric" }
      );
      out("weeks_needed").textContent = d.weeks_needed.toLocaleString();
      out("days_needed").textContent = d.days_needed.toLocaleString();
      if (icsLink) {
        const q = new URLSearchParams({
          title: title,
          total_runtime_min: String(base),
          hours_per_week: String(hpw),
        });
        icsLink.href = "/planner/export.ics?" + q.toString();
      }
      results.hidden = false;
    } catch (e) {
      /* keep last good result */
    }
  }

  const run = debounce(recalc, 200);
  [baseInput, hoursInput].forEach((el) => {
    if (el) el.addEventListener("input", run);
    if (el) el.addEventListener("change", run);
  });
  recalc();
})();
