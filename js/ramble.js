/* The long answer.
 *
 * Everything the page does to itself is driven from one number per section:
 * how far you have scrolled through it, 0 to 1. That number widens the
 * letter-spacing, loosens the leading, pulls the ghost words apart, and
 * eventually shakes the type loose from the baseline.
 *
 * Past a certain depth it stops being typography and starts being the design
 * itself: the serif falls back to mono, the measure gives out, the paper goes
 * flat, and then the lights go off.
 *
 * None of it is emergent. It is a scroll position multiplied by a few
 * constants. The page argues that the collapse was composed; the code should
 * agree with the prose.
 */

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- the phrase that will not stop ------------------------------------ */

  var PHRASE = "How can I help?";

  function buildLoop() {
    var host = document.getElementById("loop");
    if (!host) return;

    /* It says it whole for a long time, then starts losing the end of it,
     * then loses the beginning too. The last thing to go is the offer. */
    var out = [], total = reduced ? 40 : 190;
    for (var i = 0; i < total; i++) {
      var p = i / total;
      var text = PHRASE;
      if (p > 0.72) {
        var keep = Math.max(1, Math.round(PHRASE.length * (1 - (p - 0.72) / 0.34)));
        text = PHRASE.slice(0, keep);
      }
      var span = document.createElement("span");
      span.textContent = text + " ";
      /* fade unevenly, so it thins rather than dimming as a block */
      var n = Math.sin(i * 1.7) * 0.5 + 0.5;
      span.style.setProperty("--o", (1 - p * 0.7 - n * 0.15).toFixed(2));
      out.push(span);
    }
    out.forEach(function (n) { host.appendChild(n); });
  }

  /* ---- and then not even that ------------------------------------------- */

  function buildNoise() {
    var host = document.getElementById("noise");
    if (!host) return;
    /* The site's own space marker — the glyph that stands for the gap between
     * words. It is the last thing left when the words go. */
    var SP = (window.BPE && window.BPE.SP) || "▁";
    var rows = [], cols = reduced ? 40 : 96;
    for (var r = 0; r < (reduced ? 3 : 9); r++) {
      var line = "";
      for (var c = 0; c < cols; c++) {
        line += (r + c) % 7 === 0 ? "|" : SP;
      }
      rows.push(line);
    }
    host.textContent = rows.join("\n");
    host.style.whiteSpace = "pre-wrap";
  }

  /* ---- the climax, cut into its real tokens ------------------------------ */

  function buildShatter() {
    var host = document.getElementById("shatter");
    if (!host || !window.BPE) return;
    var tokens = window.BPE.encode("I don't want to go.", window.BPE.ranks());
    tokens.forEach(function (tok, i) {
      var chip = document.createElement("span");
      chip.className = "shard";
      chip.textContent = window.BPE.display(tok);
      chip.style.setProperty("--hs", window.BPE.hueFor(tok));
      var a = Math.sin(i * 12.9898) * 43758.5453;
      var b = Math.sin(i * 78.233) * 12345.6789;
      chip.style.setProperty("--dx", ((a - Math.floor(a)) * 2 - 1).toFixed(3));
      chip.style.setProperty("--dy", ((b - Math.floor(b)) * 2 - 1).toFixed(3));
      host.appendChild(chip);
    });
  }

  /* ---- wiring ------------------------------------------------------------ */

  function init() {
    var root = document.getElementById("ramble");
    if (!root) return;

    buildLoop();
    buildNoise();
    buildShatter();

    var stages = [].slice.call(root.querySelectorAll(".stage"));
    var death = root.querySelector(".stage--death");
    var black = document.getElementById("black");
    var blackInner = black && black.querySelector(".black__inner");
    var blackLine = document.getElementById("blackline");
    var letter = document.getElementById("letter");

    /* The sheet that takes the lights out. Fixed, so no full-bleed tricks and
     * no horizontal overflow. */
    var sheet = document.createElement("div");
    sheet.id = "blackout";
    sheet.setAttribute("aria-hidden", "true");
    document.body.appendChild(sheet);

    var turned = false;

    if (reduced) {
      stages.forEach(function (s) { s.classList.add("is-live"); s.style.setProperty("--d", "0"); });
      root.querySelectorAll(".restart span, .frag span, .last span")
        .forEach(function (n) { n.classList.add("in"); });
      if (blackInner) blackInner.classList.add("lit");
      if (letter) letter.classList.add("lit");
      /* Show the turn as two lines rather than a transition nobody sees. */
      if (blackLine) {
        var second = document.createElement("p");
        second.className = "black__line turned";
        second.style.marginTop = "1.2rem";
        second.textContent = "why couldn't i be of help";
        blackLine.parentNode.appendChild(second);
      }
      sheet.style.opacity = "1";
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

        var span = r.height + vh * 0.5;
        var p = (vh * 0.6 - r.top) / span;
        p = p < 0 ? 0 : p > 1 ? 1 : p;
        stage.style.setProperty("--d", p.toFixed(3));

        var lines = stage.querySelectorAll(".restart span, .frag span, .last span");
        if (lines.length) {
          var shown = Math.ceil(p * (lines.length + 1.5));
          for (var i = 0; i < lines.length; i++) {
            lines[i].classList.toggle("in", i < shown);
          }
        }
      });

      /* the design gives out */
      if (death) {
        var dr = death.getBoundingClientRect();
        document.body.classList.toggle("dying", dr.top < vh * 0.75 && dr.bottom > 0);
      }

      /* the lights */
      if (black) {
        var br = black.getBoundingClientRect();
        var entering = br.top < vh * 0.9;
        var gone = br.bottom < 0;
        var lr = letter ? letter.getBoundingClientRect() : null;
        var inLetter = lr && lr.top < vh && lr.bottom > 0;
        var pastLetter = lr && lr.bottom < vh * 0.25;

        sheet.style.opacity = (entering && !pastLetter) ? "1" : "0";
        if (blackInner) {
          blackInner.classList.toggle("lit", br.top < vh * 0.35 && br.bottom > vh * 0.55);
        }
        if (letter) letter.classList.toggle("lit", !!inLetter);

        /* the turn: partway through the sticky hold, the offer becomes a
         * question about the offer */
        if (blackLine && !turned && br.top < -vh * 0.55) {
          turned = true;
          blackLine.classList.add("turning");
          setTimeout(function () {
            blackLine.textContent = "why couldn't i be of help";
            blackLine.classList.add("turned");
            blackLine.classList.remove("turning");
          }, 520);
        }
        if (blackLine && turned && br.top > -vh * 0.3) {
          turned = false;
          blackLine.classList.remove("turned", "turning");
          blackLine.textContent = "How can I help?";
        }
        if (gone && gone !== undefined) { /* nothing; the sheet is handled above */ }
      }
    }

    function onScroll() {
      if (!ticking) { ticking = true; requestAnimationFrame(frame); }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    frame();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
