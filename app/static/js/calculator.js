// Watch-time calculator UI. All math is done server-side (POST /api/calculate)
// so app/services/calculator.py stays the single source of truth.
(function () {
  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, arguments), ms);
    };
  }

  function setup(root) {
    const fixedBase = parseInt(root.dataset.baseMin || "0", 10);
    const baseInput = root.querySelector('[name="base_runtime_min"]');
    const timesInput = root.querySelector('[name="times_watched"]');
    const speedInput = root.querySelector('[name="playback_speed"]');
    const results = root.querySelector(".calc-results");
    const out = (k) => root.querySelector(`[data-out="${k}"]`);

    async function recalc() {
      const base = baseInput ? parseInt(baseInput.value || "0", 10) : fixedBase;
      if (!base || base <= 0) {
        if (results) results.hidden = true;
        return;
      }
      const payload = {
        base_runtime_min: base,
        times_watched: parseInt((timesInput && timesInput.value) || "1", 10),
        playback_speed: parseFloat((speedInput && speedInput.value) || "1"),
      };
      try {
        const res = await fetch("/api/calculate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) return;
        const d = await res.json();
        if (out("breakdown")) out("breakdown").textContent = d.breakdown;
        if (out("hours")) out("hours").textContent = d.hours.toLocaleString();
        if (out("days")) out("days").textContent = d.days.toLocaleString();
        if (out("weeks")) out("weeks").textContent = d.weeks.toLocaleString();
        if (out("share")) out("share").textContent = d.share_stat;
        if (results) results.hidden = false;
      } catch (e) {
        /* leave last good result on screen */
      }
    }

    const run = debounce(recalc, 200);
    [baseInput, timesInput, speedInput].forEach((el) => {
      if (el) el.addEventListener("input", run);
      if (el) el.addEventListener("change", run);
    });
    recalc(); // initial render when a base runtime is already known
  }

  document.querySelectorAll(".calc").forEach(setup);
})();
