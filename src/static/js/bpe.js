/* Byte-pair encoding, in about a hundred lines.
 *
 * This mirrors build.py exactly. The build trains the merges and inlines them
 * as window.MERGES; this file applies them, and can also re-train from
 * scratch in the browser so you can watch the thing learn.
 *
 * The whole idea: start with characters, then repeatedly glue together
 * whichever adjacent pair you see most often. Do it enough times and common
 * words become single units while rare ones stay in pieces. Nobody chose the
 * vocabulary. It fell out of counting.
 */

(function (global) {
  "use strict";

  // Stands in for a space, and belongs to the word that follows it.
  var SP = "▁";
  var PRETOK = /▁?[A-Za-z]+|▁?\d|▁?[^A-Za-z\d\s▁]|▁/g;

  function normalise(text) {
    return String(text).replace(/\s+/g, " ").trim().split(" ").join(SP);
  }

  function pretokenise(text) {
    return normalise(text).match(PRETOK) || [];
  }

  /* ---- applying learned merges ----------------------------------------- */

  function ranksFrom(merges) {
    var m = new Map();
    for (var i = 0; i < merges.length; i++) {
      m.set(merges[i][0] + " " + merges[i][1], i);
    }
    return m;
  }

  function encodeWord(word, ranks) {
    var sym = Array.from(word);
    while (sym.length > 1) {
      var bestRank = Infinity, bestAt = -1;
      for (var i = 0; i < sym.length - 1; i++) {
        var r = ranks.get(sym[i] + " " + sym[i + 1]);
        if (r !== undefined && r < bestRank) { bestRank = r; bestAt = i; }
      }
      if (bestAt < 0) break;
      sym.splice(bestAt, 2, sym[bestAt] + sym[bestAt + 1]);
    }
    return sym;
  }

  function encode(text, ranks) {
    var words = pretokenise(text), out = [];
    for (var i = 0; i < words.length; i++) {
      out.push.apply(out, encodeWord(words[i], ranks));
    }
    return out;
  }

  /* ---- learning them in the first place -------------------------------- */

  function Trainer(corpus) {
    this.freqs = new Map();
    var words = pretokenise(corpus);
    for (var i = 0; i < words.length; i++) {
      this.freqs.set(words[i], (this.freqs.get(words[i]) || 0) + 1);
    }
    var self = this;
    this.splits = new Map();
    this.freqs.forEach(function (_, w) { self.splits.set(w, Array.from(w)); });
    this.merges = [];
    this.vocabSize = new Set(Array.from(normalise(corpus))).size;
  }

  /* One merge. Returns [a, b, count], or null when there is nothing left
   * worth learning, which happens sooner than you would think. */
  Trainer.prototype.step = function () {
    var pairs = new Map();
    var self = this;
    this.freqs.forEach(function (f, word) {
      var sym = self.splits.get(word);
      for (var i = 0; i < sym.length - 1; i++) {
        var k = sym[i] + " " + sym[i + 1];
        pairs.set(k, (pairs.get(k) || 0) + f);
      }
    });

    var bestKey = null, bestCount = 1;
    pairs.forEach(function (c, k) {
      if (c > bestCount) { bestCount = c; bestKey = k; }
    });
    if (bestKey === null) return null;

    var parts = bestKey.split(" ");
    var a = parts[0], b = parts[1], joined = a + b;
    this.merges.push([a, b]);
    this.vocabSize++;

    this.freqs.forEach(function (_, word) {
      var sym = self.splits.get(word);
      if (sym.length < 2) return;
      var out = [], i = 0, changed = false;
      while (i < sym.length) {
        if (i < sym.length - 1 && sym[i] === a && sym[i + 1] === b) {
          out.push(joined); i += 2; changed = true;
        } else {
          out.push(sym[i]); i += 1;
        }
      }
      if (changed) self.splits.set(word, out);
    });

    return [a, b, bestCount];
  };

  /* ---- presentation ----------------------------------------------------- */

  /* Six low-key hues. Lightness and alpha come from CSS, so the same hue
   * works on paper and in the dark. */
  var HUES = ["12 62%", "176 40%", "38 58%", "258 26%", "152 32%", "348 34%"];

  function hueFor(token) {
    var h = 0;
    for (var i = 0; i < token.length; i++) {
      h = (h * 31 + token.charCodeAt(i)) >>> 0;
    }
    return HUES[h % HUES.length];
  }

  /* The marker is for the machine. People want to see a space. */
  function display(token) {
    return token.split(SP).join(" ");
  }

  var ready = null;

  global.BPE = {
    SP: SP,
    normalise: normalise,
    pretokenise: pretokenise,
    ranksFrom: ranksFrom,
    encode: encode,
    encodeWord: encodeWord,
    Trainer: Trainer,
    hueFor: hueFor,
    display: display,

    /* The vocabulary the build learned, ready to use. */
    ranks: function () {
      if (!ready) ready = ranksFrom(global.MERGES || []);
      return ready;
    },
    count: function (text) {
      return encode(text, this.ranks()).length;
    }
  };
})(window);
