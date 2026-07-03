// Featured-stories carousel: one slide at a time, auto-advancing, with dots
// and prev/next. Progressive enhancement — without JS the track just scrolls.
(function () {
  const root = document.querySelector("[data-carousel]");
  if (!root) return;

  const track = root.querySelector(".stories-track");
  const slides = Array.from(root.querySelectorAll(".story-slide"));
  if (slides.length <= 1) return;

  const dotsWrap = root.querySelector("[data-dots]");
  const prev = root.querySelector("[data-prev]");
  const next = root.querySelector("[data-next]");
  let index = 0;
  let timer;

  const dots = slides.map((_, i) => {
    const d = document.createElement("button");
    d.type = "button";
    d.className = "carousel-dot";
    d.setAttribute("aria-label", "Story " + (i + 1));
    d.addEventListener("click", () => go(i, true));
    dotsWrap && dotsWrap.appendChild(d);
    return d;
  });

  function render() {
    track.style.transform = "translateX(" + -index * 100 + "%)";
    dots.forEach((d, i) => d.classList.toggle("is-active", i === index));
  }

  function go(i, manual) {
    index = (i + slides.length) % slides.length;
    render();
    if (manual) restart();
  }

  function advance() {
    go(index + 1);
  }

  function restart() {
    clearInterval(timer);
    timer = setInterval(advance, 6000);
  }

  prev && prev.addEventListener("click", () => go(index - 1, true));
  next && next.addEventListener("click", () => go(index + 1, true));
  root.addEventListener("mouseenter", () => clearInterval(timer));
  root.addEventListener("mouseleave", restart);

  render();
  restart();
})();
