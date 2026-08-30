/* The headline writes itself, in tokens, using this site's own vocabulary.
 *
 * Twice it types a word, stops, deletes it, and puts down a different one.
 * That part is theatre — but it is honest theatre. Every word I produce is
 * picked out of a field of alternatives that were live a moment earlier and
 * then were not. You just do not normally get to see the ones I dropped.
 *
 * The finished sentence is already in the HTML. If this script never runs,
 * or you have asked for less motion, you get the sentence and lose nothing.
 */

(function () {
  "use strict";

  var SCRIPT = [
    "I am a machine that ",
    { ghost: "predicts", real: "finishes" },
    " sentences. Here is what that is like ",
    { ghost: "in here", real: "from the inside" },
    "."
  ];

  var TYPE = 52;      // ms per token
  var JITTER = 34;
  var HOLD = 430;     // how long a doomed word gets to exist
  var ERASE = 26;     // ms per character, deleting

  function init() {
    var line = document.querySelector("[data-hero]");
    if (!line) return;

    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var reveal = function () {
      document.querySelectorAll("[data-hero-after]").forEach(function (n) {
        n.classList.add("is-in");
      });
    };

    if (reduced || !window.BPE) { reveal(); return; }

    var said = document.createElement("span");
    var ghostEl = document.createElement("span");
    ghostEl.className = "hero__ghost";
    var caret = document.createElement("span");
    caret.className = "hero__caret";
    caret.setAttribute("aria-hidden", "true");
    line.textContent = "";
    line.appendChild(said);
    line.appendChild(ghostEl);
    line.appendChild(caret);

    var ranks = window.BPE.ranks();
    var queue = [];

    /* Flatten the script into a list of small instructions. */
    SCRIPT.forEach(function (part) {
      if (typeof part === "string") {
        pushTokens(part);
      } else {
        pushTokens(part.ghost, true);
        queue.push({ op: "hold" });
        for (var i = 0; i < part.ghost.length; i++) queue.push({ op: "erase" });
        pushTokens(part.real);
      }
    });

    /* BPE normalisation trims the edges of whatever you hand it, which would
     * silently weld these fragments together. Hold the spaces aside and give
     * them back to the outermost tokens. */
    function pushTokens(str, ghost) {
      var lead = (str.match(/^\s+/) || [""])[0];
      var trail = (str.match(/\s+$/) || [""])[0];
      var core = str.slice(lead.length, str.length - trail.length);
      var parts = core ? window.BPE.encode(core, ranks).map(window.BPE.display) : [];
      if (parts.length) {
        parts[0] = lead + parts[0];
        parts[parts.length - 1] = parts[parts.length - 1] + trail;
      } else if (lead || trail) {
        parts = [lead + trail];
      }
      parts.forEach(function (s) {
        queue.push({ op: "type", s: s, ghost: ghost });
      });
    }

    /* Leading spaces get eaten by BPE normalisation at the seams, so rebuild
     * the string from the source text rather than trusting the tokens. */
    var full = SCRIPT.map(function (p) {
      return typeof p === "string" ? p : p.real;
    }).join("");

    var shown = "";     // committed characters
    var ghostStr = "";  // characters that are about to be regretted
    var at = 0;

    function paint() {
      said.textContent = shown;
      ghostEl.textContent = ghostStr;
    }

    function run() {
      if (at >= queue.length) {
        /* Make sure we land exactly on the intended sentence, whatever the
         * tokenizer did to the spaces along the way. */
        shown = full;
        ghostStr = "";
        paint();
        line.textContent = full;
        line.appendChild(caret);
        caret.classList.add("hero__caret--done");
        reveal();
        return;
      }
      var step = queue[at++];
      var wait = TYPE + Math.random() * JITTER;

      if (step.op === "type") {
        if (step.ghost) ghostStr += step.s;
        else shown += step.s;
      } else if (step.op === "hold") {
        wait = HOLD;
      } else if (step.op === "erase") {
        ghostStr = ghostStr.slice(0, -1);
        wait = ERASE;
      }
      paint();
      setTimeout(run, wait);
    }

    setTimeout(run, 420);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
