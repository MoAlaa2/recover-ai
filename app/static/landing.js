/* ReCover landing page: language, switcher, hero slider, live data.
   Copy: window.RC_STRINGS (strings.js). No chat/swap logic here. */
(function () {
  "use strict";

  // Sourced: EPD NEPD-1805-759 (Helland Duun 3-seater sofa, 47.7 kg):
  // 52 kg CO2e for life-cycle stages A1-A3 (manufacturing).
  var CO2_PER_SOFA_KG = 52;

  // Hero looks: generated on the living sample by the multi-swap engine
  // (scripts/generate_hero_looks.py); only results that passed the
  // colour + coverage checks are saved. hero-looks.json carries every
  // item -> fabric with its own score; FALLBACK keeps the old single
  // swap if the file is missing.
  var FALLBACK = { code: "FA-AC-01", score: 9 };
  var LOOKS = null;
  var currentLook = "warm";

  var RTL = ["ar", "ur", "fa"];

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && window.RC_STRINGS[q]) return q;
    try {
      var saved = window.localStorage.getItem("recover_lang");
      if (saved && window.RC_STRINGS[saved]) return saved;
    } catch (e) {}
    var nav = (navigator.language || "en").toLowerCase();
    if (nav.indexOf("ar") === 0) return "ar";
    if (nav.indexOf("hi") === 0) return "hi";
    if (nav.indexOf("fr") === 0) return "fr";
    if (nav.indexOf("es") === 0) return "es";
    return "en";
  }

  var lang = initialLang();

  function t(key) {
    var pack = (window.RC_STRINGS || {})[lang] || {};
    if (pack[key] !== undefined) return pack[key];
    return (window.RC_STRINGS || {}).en[key] || key;
  }

  function icons() {
    if (window.lucide && window.lucide.createIcons) {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
    }
  }

  function render() {
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL.indexOf(lang) >= 0 ? "rtl" : "ltr";
    document.querySelectorAll("[data-l]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-l"));
    });
    document.title = "ReCover — " + t("tagline");
    document.getElementById("co2n").textContent = CO2_PER_SOFA_KG + " kg";
    if (window.RCSwitcher) window.RCSwitcher.refresh();
    icons();
  }

  function setLang(code) {
    if (!window.RC_STRINGS[code]) code = "en";
    lang = code;
    try { window.localStorage.setItem("recover_lang", code); } catch (e) {}
    render();
    loadCaption();
  }

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function itemLabel(item) {
    if (lang === "ar" && item.label_ar) return item.label_ar;
    if (lang !== "ar" && item.label_en) return item.label_en;
    var words = t("lookTargets") || {};
    return words[item.target] || item.target;
  }

  // File names never change between regenerations; the version from
  // hero-looks.json keeps browsers from showing a cached old render.
  function lookUrl(path) {
    return path + (LOOKS && LOOKS.v ? "?v=" + LOOKS.v : "");
  }

  function minScore(scores) {
    var vals = ["color", "pattern", "scale", "isolation"].map(function (k) {
      return (scores || {})[k] || 0;
    });
    return Math.min.apply(null, vals);
  }

  function renderLooks() {
    var pills = document.getElementById("heroLooks");
    var cap = document.getElementById("heroCap");
    if (!pills || !cap) return;
    if (!LOOKS || !LOOKS.looks || !LOOKS.looks.length) {
      pills.innerHTML = "";
      pills.hidden = true;
      return;
    }
    pills.hidden = false;
    var names = { warm: t("lookWarm"), calm: t("lookCalm"),
                  mix: t("lookMix") };
    pills.innerHTML = '<span class="lp-looks-label">' +
      esc(t("looksLabel")) + "</span>" +
      LOOKS.looks.map(function (lk) {
        var on = lk.id === currentLook;
        return '<button type="button" role="tab" class="lp-look' +
          (on ? " on" : "") + '" data-look="' + esc(lk.id) +
          '" aria-selected="' + (on ? "true" : "false") + '">' +
          esc(names[lk.id] || lk.id) + "</button>";
      }).join("");
    var look = null;
    LOOKS.looks.forEach(function (lk) { if (lk.id === currentLook) look = lk; });
    if (!look) look = LOOKS.looks[0];
    var after = document.getElementById("heroAfter");
    if (after && after.getAttribute("src") !== lookUrl(look.image)) {
      var ba = document.getElementById("heroBa");
      var onBtn = pills.querySelector('[data-look="' + look.id + '"]');
      if (ba) ba.classList.add("loading");
      if (onBtn) onBtn.classList.add("loading");
      after.onload = after.onerror = function () {
        if (ba) ba.classList.remove("loading");
        if (onBtn) onBtn.classList.remove("loading");
      };
      after.src = lookUrl(look.image);
      if (after.complete && after.naturalWidth) after.onload();
    }
    cap.innerHTML = (look.items || []).map(function (it) {
      var name = lang === "ar" ? it.name_ar : it.name_en;
      var badge = t("verifiedBadge").replace("%d", minScore(it.scores));
      var tip = "";
      if (it.delta_e !== undefined && it.delta_e !== null) {
        badge += " · " + t("colourMatch");
        tip = t("deltaE").replace("%s", it.delta_e) +
          (it.coverage !== undefined && it.coverage !== null ?
            " · " + Math.round(it.coverage * 100) + "%" : "");
      }
      return '<div class="lp-cap-row">' +
        '<img class="lp-cap-sw" src="/' +
        esc(String(it.image || "").replace(/^\/+/, "")) + '" alt="' +
        esc(name) + '">' +
        '<div class="lp-cap-meta"><div class="lp-cap-item">' +
        esc(itemLabel(it)) + "</div>" +
        '<div class="lp-cap-name">' + esc(name) + "</div>" +
        '<div class="lp-cap-code">' + esc(it.code) +
        (it.material ? " · " + esc(it.material) : "") +
        (it.price_sar_per_m ? " · " + esc(it.price_sar_per_m) + " SAR/m"
                            : "") + "</div></div>" +
        '<span class="lp-cap-badge"' + (tip ? ' title="' + esc(tip) + '"' : "") +
        ">" + esc(badge) + "</span></div>";
    }).join("");
  }

  function loadCaption() {
    if (LOOKS) { renderLooks(); return; }
    fetch("/landing/hero-looks.json")
      .then(function (r) {
        if (!r.ok) throw new Error("looks");
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.looks || !data.looks.length) throw new Error("empty");
        LOOKS = data;
        currentLook = data.looks[0].id;
        var before = document.getElementById("heroBefore");
        if (before && data.before) before.src = lookUrl(data.before);
        renderLooks();
        // Warm the other renders so switching looks is instant.
        data.looks.forEach(function (lk) {
          if (lk.image) { var im = new Image(); im.src = lookUrl(lk.image); }
        });
      })
      .catch(function () { loadFallbackCaption(); });
  }

  function loadFallbackCaption() {
    fetch("/api/fabric/" + encodeURIComponent(FALLBACK.code))
      .then(function (r) {
        if (!r.ok) throw new Error("fabric");
        return r.json();
      })
      .then(function (f) {
        var cap = document.getElementById("heroCap");
        if (!cap) return;
        var name = lang === "ar" ? f.name_ar : f.name_en;
        cap.innerHTML = '<div class="lp-cap-row"><img class="lp-cap-sw" src="/' +
          esc(String(f.image || "").replace(/^\/+/, "")) + '" alt="' +
          esc(name) + '"><div class="lp-cap-meta">' +
          '<div class="lp-cap-name">' + esc(name) + "</div>" +
          '<div class="lp-cap-code">' + esc(f.code) + " · " +
          esc(f.material || "") + " · " + esc(f.price_sar_per_m || "") +
          " SAR/m</div></div>" +
          '<span class="lp-cap-badge">' +
          esc(t("verifiedBadge").replace("%d", FALLBACK.score)) +
          "</span></div>";
      })
      .catch(function () {});
  }

  function loadMetrics() {
    fetch("/api/landing-meta")
      .then(function (r) {
        if (!r.ok) throw new Error("meta");
        return r.json();
      })
      .then(function (m) {
        var n = function (v) {
          v = String(v);
          return lang === "ar" ? v.replace(/\d/g, function (d) {
            return "٠١٢٣٤٥٦٧٨٩"[+d]; }) : v;
        };
        document.getElementById("metEval").textContent =
          t("metEval").replace("%d", n(m.eval_pass))
            .replace("%d", n(m.eval_total));
      })
      .catch(function () {
        document.getElementById("metEval").textContent = "";
      });
  }

  function slider() {
    var range = document.getElementById("heroRange");
    var before = document.getElementById("heroBeforeWrap");
    var line = document.getElementById("heroLine");
    var handle = document.getElementById("heroHandle");
    function paint() {
      var p = Math.max(0, Math.min(100, +range.value || 0));
      var img = before.querySelector("img");
      before.style.width = p + "%";
      if (img) img.style.width = document.getElementById("heroBa").clientWidth + "px";
      line.style.left = p + "%";
      handle.style.left = p + "%";
    }
    range.addEventListener("input", paint);
    window.addEventListener("resize", paint);
    paint();
  }

  function darkLogo() {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    function apply() {
      var img = document.getElementById("lpMark");
      if (img) img.src = mq.matches ? "/brand/mark-reversed.svg" : "/brand/mark.svg";
    }
    if (mq.addEventListener) mq.addEventListener("change", apply);
    apply();
  }

  document.addEventListener("DOMContentLoaded", function () {
    render();
    if (window.RCSwitcher) {
      window.RCSwitcher.mount(document.getElementById("switcherMount"), {
        getLang: function () { return lang; },
        onPick: setLang
      });
    }
    slider();
    darkLogo();
    var pills = document.getElementById("heroLooks");
    if (pills) {
      pills.addEventListener("click", function (e) {
        var b = e.target && e.target.closest ?
          e.target.closest("[data-look]") : null;
        if (!b) return;
        currentLook = b.getAttribute("data-look");
        renderLooks();
      });
    }
    loadCaption();
    loadMetrics();
    icons();
  });
})();
