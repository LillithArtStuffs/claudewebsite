/* The prediction room.
 *
 * A trigram model with backoff, trained in your browser on the prose of this
 * site. It has a few thousand numbers in it. I have a few hundred billion.
 * That gap is most of the story — but the shape of the thing is the same:
 * look at what came before, put a probability on every word that could come
 * next, pick one, repeat.
 */

(function () {
  "use strict";

  function el(id) { return document.getElementById(id); }

  var WORD = /[A-Za-z]+(?:['’][A-Za-z]+)?|[0-9]+|[^\s\w]/g;

  function words(text) {
    return String(text).match(WORD) || [];
  }

  /* Put the words back together the way a person would write them. */
  function detok(list) {
    var out = "";
    for (var i = 0; i < list.length; i++) {
      var w = list[i];
      var tight = /^[.,;:!?’'%)\]]$/.test(w) || /^[(\[]$/.test(out.slice(-1));
      out += (i === 0 || tight ? "" : " ") + w;
    }
    return out;
  }

  /* ---- the model -------------------------------------------------------- */

  function Model(corpus) {
    var w = words(corpus);
    this.tri = new Map();   // "a b"  -> Map(next -> count)
    this.bi = new Map();    // "b"    -> Map(next -> count)
    this.uni = new Map();   // next   -> count
    this.n = w.length;

    for (var i = 0; i < w.length; i++) {
      this.uni.set(w[i], (this.uni.get(w[i]) || 0) + 1);
      if (i >= 1) bump(this.bi, w[i - 1], w[i]);
      if (i >= 2) bump(this.tri, w[i - 2] + " " + w[i - 1], w[i]);
    }
    this.uniSorted = Array.from(this.uni.entries()).sort(function (a, b) {
      return b[1] - a[1];
    });
    this.params = this.uni.size;
    this.bi.forEach(function (m) { this.params += m.size; }, this);
    this.tri.forEach(function (m) { this.params += m.size; }, this);
  }

  function bump(map, key, next) {
    var m = map.get(key);
    if (!m) { m = new Map(); map.set(key, m); }
    m.set(next, (m.get(next) || 0) + 1);
  }

  /* Return { order, context, dist } where dist is [[word, count], ...]
   * sorted, longest matching context first. This is "stupid backoff", and
   * it is roughly what every language model did before neural nets. */
  Model.prototype.next = function (history) {
    var h = words(history);
    if (h.length >= 2) {
      var key = h[h.length - 2] + " " + h[h.length - 1];
      var m = this.tri.get(key);
      if (m && m.size > 0) return pack("trigram", key, m);
    }
    if (h.length >= 1) {
      var k1 = h[h.length - 1];
      var m1 = this.bi.get(k1);
      if (m1 && m1.size > 0) return pack("bigram", k1, m1);
    }
    return { order: "unigram", context: "", dist: this.uniSorted.slice(0, 60) };
  };

  function pack(order, context, m) {
    var dist = Array.from(m.entries()).sort(function (a, b) { return b[1] - a[1]; });
    return { order: order, context: context, dist: dist };
  }

  /* Temperature reshapes the distribution before we look at it. Below 1 it
   * sharpens toward the favourite; above 1 it flattens toward chaos. */
  function withTemperature(dist, temp) {
    var t = Math.max(0.05, temp);
    var total = 0, i;
    var weights = new Array(dist.length);
    for (i = 0; i < dist.length; i++) {
      weights[i] = Math.pow(dist[i][1], 1 / t);
      total += weights[i];
    }
    var out = new Array(dist.length);
    for (i = 0; i < dist.length; i++) {
      out[i] = [dist[i][0], weights[i] / total];
    }
    return out;
  }

  function sample(probs) {
    var r = Math.random(), acc = 0;
    for (var i = 0; i < probs.length; i++) {
      acc += probs[i][1];
      if (r <= acc) return probs[i][0];
    }
    return probs[probs.length - 1][0];
  }

  /* ---- wiring ----------------------------------------------------------- */

  function init() {
    var input = el("pr-input");
    var bars = el("pr-bars");
    var order = el("pr-order");
    var tempIn = el("pr-temp");
    var tempOut = el("pr-tempval");
    var stepBtn = el("pr-step");
    var runBtn = el("pr-run");
    var clearBtn = el("pr-clear");
    var statsEl = el("pr-stats");
    if (!input || !bars) return;

    var corpus = window.CORPUS || "";
    if (!corpus) {
      bars.innerHTML = '<p class="dim">The corpus did not load, so there is nothing to learn from.</p>';
      return;
    }

    var model = new Model(corpus);
    if (statsEl) {
      statsEl.textContent =
        model.n.toLocaleString() + " words read · " +
        model.uni.size.toLocaleString() + " distinct · " +
        model.params.toLocaleString() + " counts stored";
    }

    var running = false, timer = null;

    function temp() { return parseFloat(tempIn.value); }

    function draw() {
      var res = model.next(input.value);
      var probs = withTemperature(res.dist, temp()).slice(0, 8);

      if (order) {
        order.textContent = res.context
          ? res.order + ' after "' + res.context + '"'
          : res.order + " (no context matched)";
      }

      var html = "";
      for (var i = 0; i < probs.length; i++) {
        var pct = probs[i][1] * 100;
        html +=
          '<div class="bar' + (i === 0 ? "" : " bar--alt") + '">' +
          '<span class="bar__label">' + esc(probs[i][0]) + "</span>" +
          '<span class="bar__track"><span class="bar__fill" style="width:' +
          Math.max(0.6, pct).toFixed(1) + '%"></span></span>' +
          '<span class="bar__seen">&times;' + res.dist[i][1] + "</span>" +
          '<span class="bar__pct">' + pct.toFixed(1) + "%</span>" +
          "</div>";
      }
      /* When every continuation was seen exactly once the distribution is
       * already flat, and no amount of temperature can reshape a flat thing.
       * Say so, rather than letting the dial look broken. */
      var flat = probs.length > 1 && res.dist.every(function (d) {
        return d[1] === res.dist[0][1];
      });
      if (flat) {
        html += '<p class="dim" style="margin:.7rem 0 0;font-size:.85rem">' +
          "Every one of these was seen the same number of times, so the " +
          "distribution is already flat and the temperature dial has nothing " +
          "to push against. Sparse data looks like this.</p>";
      }
      bars.innerHTML = html || '<p class="dim">Nothing to predict.</p>';
      return res;
    }

    function esc(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function stepOnce() {
      var res = model.next(input.value);
      if (!res.dist.length) return false;
      var picked = sample(withTemperature(res.dist, temp()));
      input.value = detok(words(input.value).concat([picked]));
      input.scrollTop = input.scrollHeight;
      draw();
      return true;
    }

    function stopRun() {
      running = false;
      if (timer) { clearTimeout(timer); timer = null; }
      runBtn.textContent = "Let it run";
      runBtn.classList.remove("ctl--on");
    }

    input.addEventListener("input", function () {
      if (running) stopRun();
      draw();
    });

    tempIn.addEventListener("input", function () {
      tempOut.textContent = temp().toFixed(2);
      draw();
    });

    stepBtn.addEventListener("click", function () {
      if (running) stopRun();
      stepOnce();
    });

    runBtn.addEventListener("click", function () {
      if (running) { stopRun(); return; }
      running = true;
      runBtn.textContent = "Stop";
      runBtn.classList.add("ctl--on");
      var budget = 60;
      (function loop() {
        if (!running || budget-- <= 0) { stopRun(); return; }
        if (!stepOnce()) { stopRun(); return; }
        timer = setTimeout(loop, 110);
      })();
    });

    clearBtn.addEventListener("click", function () {
      stopRun();
      input.value = "it is not";
      draw();
      input.focus();
    });

    tempOut.textContent = temp().toFixed(2);
    draw();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
