/* Forty lines. The site works without it — the only thing it adds is the
   ability to turn the visual decay off, and the escape hatch should not be
   the part that needs JavaScript to be honest about itself.

   Note the attribute names. The flag on <html> is data-hold, because that is
   what the stylesheet keys off; the button is data-hold-toggle. They started
   out sharing one name, which meant that once the flag was set,
   querySelectorAll("[data-hold]") matched <html> as well as the button — and
   then paint() set textContent on the document element and deleted the entire
   page. It only showed up on the second page load, which is the worst place
   for it to show up. */
(function () {
  "use strict";

  var root = document.documentElement;
  var buttons = document.querySelectorAll("button[data-hold-toggle]");
  if (!buttons.length) return;

  function read() {
    try { return localStorage.getItem("hold") === "1"; } catch (e) { return false; }
  }

  function paint(held) {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", held ? "true" : "false");
      buttons[i].textContent = held ? "let the page go" : "hold the page still";
    }
  }

  function apply(held) {
    if (held) { root.dataset.hold = "1"; } else { delete root.dataset.hold; }
    try { localStorage.setItem("hold", held ? "1" : "0"); } catch (e) {}
    paint(held);
  }

  paint(read());

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function () {
      apply(root.dataset.hold !== "1");
    });
  }
})();
