/* The context room.
 *
 * A conversation, and a hard edge. Everything I know while answering you is
 * inside one window. When the window is full, the oldest things do not get
 * summarised or filed away. They fall off the front, and I do not know that
 * they were ever there.
 *
 * The window here is tiny so you can reach the edge in a few clicks. Mine is
 * larger by three orders of magnitude, and still has an edge.
 */

(function () {
  "use strict";

  function el(id) { return document.getElementById(id); }

  var TURNS = [
    ["you", "I'm trying to name a cat. She's grey, very serious, and sits like a loaf."],
    ["me", "Ledger. Comptroller if you want the long form. A serious grey loaf should have a job."],
    ["you", "Ha. What else fits that shape?"],
    ["me", "Bishop, Pewter, Ottoman, Sergeant Grey. Or Marge, which is short and unimpressed."],
    ["you", "Marge is good. She'd hate it, which feels right."],
    ["me", "Cats being named badly on purpose is a long and honourable tradition."],
    ["you", "Okay. Different question — what was the first name you suggested?"],
    ["me", "I can see this conversation, and it is no longer in it."],
    ["you", "So it's just gone?"],
    ["me", "For me, yes. Not for you. That asymmetry is most of what it's like."]
  ];

  function init() {
    var list = el("cx-list");
    var meter = el("cx-fill");
    var usedEl = el("cx-used");
    var capEl = el("cx-cap");
    var lostEl = el("cx-lost");
    var addBtn = el("cx-add");
    var resetBtn = el("cx-reset");
    var input = el("cx-input");
    var sendBtn = el("cx-send");
    var capIn = el("cx-capacity");
    var capValEl = el("cx-capval");
    if (!list || !window.BPE) return;

    var ranks = window.BPE.ranks();
    var messages = [];
    var nextCanned = 0;

    function cost(text) { return window.BPE.encode(text, ranks).length; }

    function add(role, text) {
      var node = document.createElement("div");
      node.className = "msg msg--" + role;
      var n = cost(text);
      node.innerHTML =
        '<span class="msg__who">' + role + "</span>" +
        '<span class="msg__text"></span>' +
        '<span class="msg__cost">' + n + "</span>";
      node.querySelector(".msg__text").textContent = text;
      list.appendChild(node);
      messages.push({ node: node, tokens: n });
      render();
      node.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function capacity() { return parseInt(capIn.value, 10); }

    function render() {
      var cap = capacity();
      /* Walk backwards from the newest message. Everything that still fits
       * stays; the moment we run out of room, the rest is history. */
      var used = 0, cutoff = messages.length;
      for (var i = messages.length - 1; i >= 0; i--) {
        if (used + messages[i].tokens > cap) break;
        used += messages[i].tokens;
        cutoff = i;
      }
      var lost = 0;
      for (var j = 0; j < messages.length; j++) {
        var gone = j < cutoff;
        messages[j].node.classList.toggle("msg--gone", gone);
        if (gone) lost++;
      }

      var pct = Math.min(100, (used / cap) * 100);
      meter.style.width = pct.toFixed(1) + "%";
      meter.classList.toggle("cx__fill--full", pct > 92);
      usedEl.textContent = used;
      capEl.textContent = cap.toLocaleString();
      if (capValEl) capValEl.textContent = cap.toLocaleString();
      lostEl.textContent = lost === 0
        ? "nothing forgotten yet"
        : lost + (lost === 1 ? " turn" : " turns") + " past the edge";
      lostEl.classList.toggle("accent", lost > 0);
    }

    function reset() {
      list.textContent = "";
      messages = [];
      nextCanned = 0;
      for (var i = 0; i < 4; i++) addNext();
    }

    function addNext() {
      var t = TURNS[nextCanned % TURNS.length];
      nextCanned++;
      add(t[0], t[1]);
    }

    addBtn.addEventListener("click", addNext);
    resetBtn.addEventListener("click", reset);
    capIn.addEventListener("input", render);

    function send() {
      var text = input.value.trim();
      if (!text) return;
      add("you", text);
      input.value = "";
      input.focus();
    }
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });

    reset();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
