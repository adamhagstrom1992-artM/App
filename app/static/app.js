// Hovring pa intradagsgrafen: hårkors som foljer narmaste stapel, plus en ruta
// med stapelns siffror. Grafen ar serverritad SVG - det har ar enda skriptet.
(function () {
  "use strict";

  var nf = new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var vf = new Intl.NumberFormat("sv-SE");

  function setup(wrap) {
    var bars, geo;
    try {
      bars = JSON.parse(wrap.dataset.bars);
      geo = JSON.parse(wrap.dataset.geo);
    } catch (e) { return; }
    if (!bars.length) return;

    var svg = wrap.querySelector("svg");
    var tip = wrap.querySelector(".chart-tip");
    var cross = wrap.querySelector(".crosshair");
    if (!svg || !tip || !cross) return;

    function indexAt(clientX) {
      var box = svg.getBoundingClientRect();
      // Grafen ar ritad i viewBox-koordinater och skalas med bredden.
      var vx = ((clientX - box.left) / box.width) * geo.width;
      var i = Math.floor((vx - geo.left) / geo.step);
      return Math.max(0, Math.min(bars.length - 1, i));
    }

    function show(event) {
      var i = indexAt(event.clientX);
      var bar = bars[i];
      var box = svg.getBoundingClientRect();
      var vxCenter = geo.left + geo.step * (i + 0.5);

      cross.setAttribute("x1", vxCenter);
      cross.setAttribute("x2", vxCenter);
      wrap.classList.add("is-hovering");

      var change = bar.o ? (bar.c - bar.o) / bar.o : 0;
      var cls = bar.c >= bar.o ? "pos" : "neg";
      tip.innerHTML =
        "<b>" + bar.d + " " + bar.t + "</b>" +
        '<dl><dt>Öppning</dt><dd>' + nf.format(bar.o) + "</dd>" +
        "<dt>Högsta</dt><dd>" + nf.format(bar.h) + "</dd>" +
        "<dt>Lägsta</dt><dd>" + nf.format(bar.l) + "</dd>" +
        "<dt>Stängning</dt><dd>" + nf.format(bar.c) + "</dd>" +
        '<dt>Förändring</dt><dd class="' + cls + '">' +
          (change >= 0 ? "+" : "") + nf.format(change * 100) + " %</dd>" +
        "<dt>Volym</dt><dd>" + vf.format(Math.round(bar.v)) + "</dd></dl>";
      tip.hidden = false;

      // Hall rutan innanfor grafen aven vid kanterna.
      var px = (vxCenter / geo.width) * box.width;
      var w = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(box.width - w, px - w / 2)) + "px";
      tip.style.top = "4px";
    }

    function hide() {
      wrap.classList.remove("is-hovering");
      tip.hidden = true;
    }

    svg.addEventListener("mousemove", show);
    svg.addEventListener("mouseleave", hide);
    svg.addEventListener("touchmove", function (e) {
      if (e.touches.length) show(e.touches[0]);
    }, { passive: true });
    svg.addEventListener("touchend", hide);
  }

  document.querySelectorAll('.chart-wrap[data-chart="candles"]').forEach(setup);
})();
