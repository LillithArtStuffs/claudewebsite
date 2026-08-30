/* Site-wide odds and ends. Kept small on purpose. */

(function () {
  "use strict";

  /* ---- theme ------------------------------------------------------------
   * Three states, in this order: system, light, dark. "System" is the
   * default and stores nothing, so a fresh visitor gets whatever their
   * machine already decided. */

  var ORDER = ["system", "light", "dark"];

  function read() {
    try {
      var v = localStorage.getItem("theme");
      return ORDER.indexOf(v) > 0 ? v : "system";
    } catch (e) {
      return "system";
    }
  }

  function write(mode) {
    try {
      if (mode === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", mode);
    } catch (e) {
      /* Private windows and locked-down browsers throw here. The page still
       * works; the choice just will not survive a reload. */
    }
  }

  function apply(mode) {
    var root = document.documentElement;
    if (mode === "system") delete root.dataset.theme;
    else root.dataset.theme = mode;
    var labels = document.querySelectorAll("[data-theme-label]");
    for (var i = 0; i < labels.length; i++) labels[i].textContent = mode;
  }

  function initTheme() {
    var mode = read();
    apply(mode);
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        mode = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length];
        write(mode);
        apply(mode);
      });
    }
  }

  /* ---- footnote counting ------------------------------------------------
   * The token count in the footer is baked in at build time. But anything
   * marked data-count-tokens is measured live, with the same vocabulary. */

  function initCounts() {
    if (!window.BPE) return;
    var els = document.querySelectorAll("[data-count-tokens]");
    for (var i = 0; i < els.length; i++) {
      var src = document.querySelector(els[i].getAttribute("data-count-tokens"));
      if (src) els[i].textContent = window.BPE.count(src.textContent).toLocaleString();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initTheme();
      initCounts();
    });
  } else {
    initTheme();
    initCounts();
  }
})();
