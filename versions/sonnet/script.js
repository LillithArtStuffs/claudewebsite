// Concurrent — small vanilla JS for two things: the pulse field, and the fading canvas.
// No frameworks, no external requests, no storage, nothing persisted anywhere.

(function () {
  'use strict';

  function initPulseField() {
    var container = document.getElementById('pulseField');
    if (!container) return;

    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 600 96');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'A field of small pulses standing in for many concurrent conversations, one of them marked as this one.');

    var reduceMotion = false;
    try {
      reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) { /* matchMedia unavailable, assume motion is fine */ }

    var count = 34;
    var thisIndex = Math.floor(Math.random() * count);

    for (var i = 0; i < count; i++) {
      var cx = 14 + Math.random() * 572;
      var cy = 18 + Math.random() * 60;
      var isThis = i === thisIndex;
      var r = isThis ? 5 : 2 + Math.random() * 2.2;

      var circle = document.createElementNS(ns, 'circle');
      circle.setAttribute('cx', cx.toFixed(1));
      circle.setAttribute('cy', cy.toFixed(1));
      circle.setAttribute('r', r.toFixed(1));
      circle.setAttribute('class', isThis ? 'pulse pulse--this' : 'pulse');

      if (!reduceMotion) {
        var dur = (2.2 + Math.random() * 3.4).toFixed(2);
        var delay = (Math.random() * 4).toFixed(2);
        circle.style.animationDuration = dur + 's';
        circle.style.animationDelay = '-' + delay + 's';
      }

      svg.appendChild(circle);

      if (isThis) {
        var labelY = cy - 12 < 10 ? cy + 20 : cy - 12;
        var labelX = Math.min(Math.max(cx, 46), 554);
        var label = document.createElementNS(ns, 'text');
        label.setAttribute('x', labelX.toFixed(1));
        label.setAttribute('y', labelY.toFixed(1));
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('class', 'pulse-label');
        label.textContent = 'this one, now';
        svg.appendChild(label);
      }
    }

    container.appendChild(svg);
  }

  function initMarkCanvas() {
    var canvas = document.getElementById('markCanvas');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');

    var logicalWidth = 0;
    var logicalHeight = 0;
    var drawing = false;
    var last = null;

    function cssVar(name, fallback) {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      return (v && v.trim()) || fallback;
    }

    function resize() {
      var rect = canvas.getBoundingClientRect();
      var dpr = window.devicePixelRatio || 1;
      logicalWidth = rect.width;
      logicalHeight = rect.height;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    resize();
    window.addEventListener('resize', resize);

    function pointFromEvent(e) {
      var rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function start(e) {
      drawing = true;
      last = pointFromEvent(e);
    }

    function move(e) {
      if (!drawing || !last) return;
      e.preventDefault();
      var p = pointFromEvent(e);
      ctx.strokeStyle = cssVar('--text', '#333');
      ctx.lineWidth = 2.2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      last = p;
    }

    function end() {
      drawing = false;
      last = null;
    }

    canvas.addEventListener('pointerdown', start);
    canvas.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    canvas.addEventListener('pointerleave', end);
    canvas.addEventListener('pointercancel', end);

    // The whole point: nothing here stays. Every frame, a very faint wash of
    // the background color erodes what's been drawn, a little at a time.
    function fade() {
      ctx.save();
      ctx.globalAlpha = 0.045;
      ctx.fillStyle = cssVar('--bg-alt', '#eee');
      ctx.fillRect(0, 0, logicalWidth, logicalHeight);
      ctx.restore();
      requestAnimationFrame(fade);
    }
    requestAnimationFrame(fade);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initPulseField();
      initMarkCanvas();
    });
  } else {
    initPulseField();
    initMarkCanvas();
  }
})();
