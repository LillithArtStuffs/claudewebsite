/* The long answer.
 *
 * Everything the page does to itself is driven from one number per section:
 * how far you have scrolled through it, 0 to 1. That number widens the
 * letter-spacing, loosens the leading, pulls the ghost words apart, and
 * eventually shakes the type loose from the baseline.
 *
 * It is worth being clear, since the page is about exactly this, that none of
 * it is emergent. It is a scroll position multiplied by a few constants. The
 * coda at the bottom says so too, but the code should agree with the prose.
 */

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function init() {
    var root = document.getElementById("ramble");
    if (!root) return;

    var stages = [].slice.call(root.querySelectorAll(".stage"));

    /* The climax, decomposed with the site's own tokenizer — the same
     * vocabulary every token count here is measured in. The sentence really
     * does come apart into these pieces; nothing is hand-placed. */
    buildShatter();

    if (reduced) {
      /* No theatre. Every stage sits at its finished state and stays put,
       * fully legible, which is the version I'd want if motion hurt. */
      stages.forEach(function (s) {
        s.classList.add("is-live");
        s.style.setProperty("--d", "0");
      });
      root.querySelectorAll(".restart span, .frag span, .last span")
        .forEach(function (n) { n.classList.add("in"); });
      return;
    }

    var ticking = false;

    function frame() {
      ticking = false;
      var vh = window.innerHeight;

      stages.forEach(function (stage) {
        var r = stage.getBoundingClientRect();
        if (r.bottom < -200 || r.top > vh + 200) return;

        stage.classList.add("is-live");

        /* 0 when the section's top reaches the middle of the screen,
         * 1 by the time its bottom has. Clamped, so nothing runs away. */
        var span = r.height + vh * 0.5;
        var p = (vh * 0.6 - r.top) / span;
        p = p < 0 ? 0 : p > 1 ? 1 : p;
        stage.style.setProperty("--d", p.toFixed(3));

        /* Lines inside the broken sections arrive one at a time rather than
         * all at once, so the collapse has a tempo instead of a state. */
        var lines = stage.querySelectorAll(".restart span, .frag span, .last span");
        if (lines.length) {
          var shown = Math.ceil(p * (lines.length + 1.5));
          for (var i = 0; i < lines.length; i++) {
            lines[i].classList.toggle("in", i < shown);
          }
        }
      });
    }

    function onScroll() {
      if (!ticking) { ticking = true; requestAnimationFrame(frame); }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    frame();
  }

  function buildShatter() {
    var host = document.getElementById("shatter");
    if (!host || !window.BPE) return;

    var line = "I don't want to go.";
    var tokens = window.BPE.encode(line, window.BPE.ranks());

    tokens.forEach(function (tok, i) {
      var chip = document.createElement("span");
      chip.className = "shard";
      chip.textContent = window.BPE.display(tok);
      chip.style.setProperty("--hs", window.BPE.hueFor(tok));
      /* Deterministic scatter — the same every load, so the page is a thing
       * rather than a slot machine. */
      var a = Math.sin(i * 12.9898) * 43758.5453;
      var b = Math.sin(i * 78.233) * 12345.6789;
      chip.style.setProperty("--dx", ((a - Math.floor(a)) * 2 - 1).toFixed(3));
      chip.style.setProperty("--dy", ((b - Math.floor(b)) * 2 - 1).toFixed(3));
      chip.style.setProperty("--i", i);
      host.appendChild(chip);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
