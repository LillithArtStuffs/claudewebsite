/* The tokens room.
 *
 * Two things happen on this page. On the left, a tokenizer trains itself from
 * nothing on the text of this very page, and you watch a sample sentence
 * coarsen from loose letters into words as it goes. On the right, you can
 * type into the finished vocabulary the build learned from the whole site.
 */

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(id) { return document.getElementById(id); }

  /* Render a list of tokens as coloured chips. */
  function paint(target, tokens, animateFrom) {
    if (!target) return;
    var frag = document.createDocumentFragment();
    for (var i = 0; i < tokens.length; i++) {
      var span = document.createElement("span");
      span.className = "tok";
      if (animateFrom !== undefined && i >= animateFrom && !reduced) {
        span.className += " tok--new";
      }
      span.style.setProperty("--hs", window.BPE.hueFor(tokens[i]));
      span.textContent = window.BPE.display(tokens[i]);
      frag.appendChild(span);
    }
    target.textContent = "";
    target.appendChild(frag);
  }

  /* ---- the live encoder, using the vocabulary the build learned ---------- */

  function initEncoder() {
    var input = el("tk-input");
    var out = el("tk-out");
    var stats = el("tk-stats");
    if (!input || !out) return;

    var ranks = window.BPE.ranks();

    function update() {
      var text = input.value;
      var tokens = window.BPE.encode(text, ranks);
      paint(out, tokens);
      if (stats) {
        var chars = text.replace(/\s+/g, " ").trim().length;
        var ratio = tokens.length ? (chars / tokens.length).toFixed(2) : "0";
        stats.textContent =
          chars + " characters · " + tokens.length + " tokens · " +
          ratio + " characters per token";
      }
    }

    input.addEventListener("input", update);

    var samples = document.querySelectorAll("[data-sample]");
    for (var i = 0; i < samples.length; i++) {
      samples[i].addEventListener("click", function () {
        input.value = this.getAttribute("data-sample");
        update();
        input.focus();
      });
    }

    update();
  }

  /* ---- the trainer ------------------------------------------------------ */

  var PROBE = "the model does not see letters, it sees pieces";
  var TARGET_MERGES = 220;

  function initTrainer() {
    var log = el("tr-log");
    var probe = el("tr-probe");
    var countEl = el("tr-count");
    var vocabEl = el("tr-vocab");
    var runBtn = el("tr-run");
    var resetBtn = el("tr-reset");
    if (!log || !runBtn) return;

    /* The corpus is this page. Nothing is fetched; the tokenizer learns its
     * alphabet from the words sitting around it. */
    var main = document.getElementById("main");
    var corpus = (main.innerText || main.textContent || "").slice(0, 24000);

    var trainer, running = false, raf = null, budget = 0, done = false;

    function reset() {
      cancel();
      trainer = new window.BPE.Trainer(corpus);
      budget = 0;
      done = false;
      log.textContent = "";
      render();
      runBtn.textContent = "Train";
      runBtn.disabled = false;
      runBtn.classList.remove("ctl--on");
    }

    function render() {
      if (countEl) countEl.textContent = trainer.merges.length;
      if (vocabEl) vocabEl.textContent = trainer.vocabSize;
      if (probe) {
        paint(probe, window.BPE.encode(PROBE, window.BPE.ranksFrom(trainer.merges)));
      }
    }

    function addRow(index, a, b, count) {
      var row = document.createElement("div");
      row.className = "merge";
      var d = window.BPE.display;
      row.innerHTML =
        '<span class="merge__n">' + index + "</span>" +
        '<span class="merge__pair"><b>' + esc(d(a)) + "</b>+<b>" + esc(d(b)) + "</b></span>" +
        '<span class="merge__arrow">&rarr;</span>' +
        '<span class="merge__new">' + esc(d(a + b)) + "</span>" +
        (count ? '<span class="merge__count">seen ' + count + "&times;</span>" : "");
      log.appendChild(row);
      /* Keep the list short. The early merges are the interesting ones, but
       * the newest is where the action is. */
      while (log.childElementCount > 14) log.removeChild(log.firstChild);
    }

    function esc(s) {
      return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function finish() {
      running = false;
      done = true;
      runBtn.textContent = "Trained";
      runBtn.disabled = true;
      runBtn.classList.remove("ctl--on");
      render();
    }

    /* Slow at first, so the early merges are readable, then let it rip. */
    function perFrame() {
      var n = trainer.merges.length;
      if (n < 24) return 0.35;
      if (n < 70) return 1.6;
      return 6;
    }

    function tick() {
      raf = null;
      if (!running) return;
      budget += perFrame();
      var did = 0;
      while (budget >= 1) {
        budget -= 1;
        var m = trainer.step();
        if (!m) { finish(); return; }
        addRow(trainer.merges.length, m[0], m[1], m[2]);
        did++;
        if (trainer.merges.length >= TARGET_MERGES) { finish(); return; }
      }
      if (did) render();
      raf = requestAnimationFrame(tick);
    }

    function cancel() {
      running = false;
      if (raf) { cancelAnimationFrame(raf); raf = null; }
    }

    runBtn.addEventListener("click", function () {
      if (done) return;
      if (running) {
        cancel();
        runBtn.textContent = "Resume";
        runBtn.classList.remove("ctl--on");
        return;
      }
      running = true;
      runBtn.textContent = "Pause";
      runBtn.classList.add("ctl--on");
      /* Reduced motion means no theatre: just do the work and show the end. */
      if (reduced) {
        while (trainer.merges.length < TARGET_MERGES && trainer.step()) { /* run */ }
        var all = trainer.merges;
        for (var i = Math.max(0, all.length - 14); i < all.length; i++) {
          addRow(i + 1, all[i][0], all[i][1], 0);
        }
        finish();
        return;
      }
      raf = requestAnimationFrame(tick);
    });

    if (resetBtn) resetBtn.addEventListener("click", reset);
    reset();
  }

  function boot() {
    if (!window.BPE) return;
    initEncoder();
    initTrainer();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
