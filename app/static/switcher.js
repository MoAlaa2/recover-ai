/* ReCover shared language switcher. Mount with:
     RCSwitcher.mount(el, { getLang: () => code, onPick: (code) => {} })
   Renders the pill button + popover (bottom sheet under 720px).
   Depends on window.RC_STRINGS / RC_LOCALES / RC_COMING (strings.js). */
window.RCSwitcher = (function () {
  var mounts = [];

  function t(lang, key) {
    var pack = (window.RC_STRINGS || {})[lang] || {};
    if (pack[key] !== undefined) return pack[key];
    return (window.RC_STRINGS || {}).en[key] || key;
  }

  function icons(root) {
    if (window.lucide && window.lucide.createIcons) {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
    }
  }

  function mount(el, opts) {
    var st = {
      el: el,
      getLang: opts.getLang,
      onPick: opts.onPick,
      open: false,
      lastFocus: null
    };
    el.innerHTML =
      '<button type="button" class="rcsw-btn" aria-haspopup="dialog">' +
      '<i data-lucide="globe" aria-hidden="true"></i>' +
      '<span class="rcsw-cur"></span>' +
      '<span class="rcsw-short" aria-hidden="true"></span>' +
      '<span class="rcsw-badge"></span>' +
      '<span class="rcsw-chev"><i data-lucide="chevron-down" aria-hidden="true"></i></span>' +
      "</button>" +
      '<div class="rcsw-pop" role="dialog" aria-modal="true" hidden>' +
      '<div class="rcsw-grab" aria-hidden="true"></div>' +
      '<div class="rcsw-head"><div class="rcsw-titles">' +
      '<p class="rcsw-title"></p><p class="rcsw-cap"></p></div>' +
      '<button type="button" class="rcsw-close" aria-label="×">×</button></div>' +
      '<p class="rcsw-label"><span class="rcsw-dot"></span><span class="rcsw-live-t"></span></p>' +
      '<div class="rcsw-grid"></div>' +
      '<hr class="rcsw-div">' +
      '<p class="rcsw-label"><span class="rcsw-soon-t"></span></p>' +
      '<div class="rcsw-soon"></div>' +
      '<p class="rcsw-foot"></p>' +
      "</div>";
    st.btn = el.querySelector(".rcsw-btn");
    st.pop = el.querySelector(".rcsw-pop");
    st.btn.addEventListener("click", function () {
      toggle(st);
    });
    el.querySelector(".rcsw-close").addEventListener("click", function () {
      close(st);
    });
    st.pop.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { close(st); return; }
      if (e.key !== "Tab") return;
      var f = focusables(st);
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    });
    document.addEventListener("pointerdown", function (e) {
      if (st.open && !st.pop.hidden && !el.contains(e.target)) close(st);
    });
    // Swipe down on the grab handle dismisses the sheet (mobile).
    var grab = el.querySelector(".rcsw-grab"), y0 = null;
    st.pop.addEventListener("touchstart", function (e) {
      y0 = e.touches[0].clientY;
    }, { passive: true });
    st.pop.addEventListener("touchmove", function (e) {
      if (y0 === null) return;
      var dy = e.touches[0].clientY - y0;
      if (dy > 0) st.pop.style.transform = "translateY(" + dy + "px)";
    }, { passive: true });
    st.pop.addEventListener("touchend", function (e) {
      var dy = e.changedTouches[0].clientY - (y0 || 0);
      y0 = null;
      st.pop.style.transform = "";
      if (dy > 90) close(st);
    });
    mounts.push(st);
    render(st);
    return st;
  }

  function focusables(st) {
    return Array.prototype.slice.call(
      st.pop.querySelectorAll("button:not([disabled])"));
  }

  function render(st) {
    var lang = st.getLang();
    var cur = null;
    (window.RC_LOCALES || []).forEach(function (l) {
      if (l.code === lang) cur = l;
    });
    cur = cur || window.RC_LOCALES[0];
    st.el.querySelector(".rcsw-cur").textContent = cur.native;
    st.el.querySelector(".rcsw-short").textContent =
      (cur.code || "en").toUpperCase();
    st.el.querySelector(".rcsw-badge").textContent =
      t(lang, "swBadge").replace("%d", window.RC_LOCALES.length);
    st.el.querySelector(".rcsw-title").textContent = t(lang, "swTitle");
    st.el.querySelector(".rcsw-cap").textContent = t(lang, "swCaption");
    st.el.querySelector(".rcsw-live-t").textContent = t(lang, "swLive");
    st.el.querySelector(".rcsw-soon-t").textContent = t(lang, "swSoon");
    st.el.querySelector(".rcsw-foot").textContent = t(lang, "swFooter");
    st.el.querySelector(".rcsw-close").setAttribute("aria-label",
      t(lang, "swClose"));
    var grid = st.el.querySelector(".rcsw-grid");
    grid.innerHTML = "";
    (window.RC_LOCALES || []).forEach(function (l) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "rcsw-live";
      if (l.code === lang) b.setAttribute("aria-current", "true");
      b.innerHTML = '<span class="t"><span class="n"></span>' +
        '<span class="e"></span>' +
        '<span class="rcsw-beta" hidden></span></span>' +
        '<span class="ck"><i data-lucide="check" aria-hidden="true"></i></span>';
      b.querySelector(".n").textContent = l.native;
      b.querySelector(".e").textContent = l.name;
      if (l.code === "hi" || l.code === "fr" || l.code === "es") {
        var beta = b.querySelector(".rcsw-beta");
        beta.textContent = t(lang, "betaTag");
        beta.hidden = false;
      }
      (function (code) {
        b.addEventListener("click", function () {
          close(st);
          st.onPick(code);
        });
      })(l.code);
      grid.appendChild(b);
    });
    var soon = st.el.querySelector(".rcsw-soon");
    soon.innerHTML = "";
    (window.RC_COMING || []).forEach(function (name) {
      var s = document.createElement("span");
      s.textContent = name;
      s.setAttribute("aria-disabled", "true");
      soon.appendChild(s);
    });
    icons(st.el);
  }

  function place(st) {
    if (window.innerWidth < 720) {
      st.pop.style.left = "";
      st.pop.style.top = "";
      return;
    }
    var r = st.btn.getBoundingClientRect();
    var w = Math.min(380, window.innerWidth - 32);
    var left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8));
    st.pop.style.left = left + "px";
    st.pop.style.top = (r.bottom + 8) + "px";
  }

  function toggle(st) {
    if (st.open) { close(st); return; }
    render(st);
    st.lastFocus = document.activeElement;
    st.pop.hidden = false;
    st.open = true;
    place(st);
    var f = focusables(st);
    if (f.length) f[0].focus();
  }

  function close(st) {
    if (!st.open) return;
    st.open = false;
    st.pop.hidden = true;
    st.pop.style.transform = "";
    if (st.lastFocus && st.lastFocus.focus) st.lastFocus.focus();
  }

  function refresh() {
    mounts.forEach(render);
  }

  return { mount: mount, refresh: refresh };
})();
