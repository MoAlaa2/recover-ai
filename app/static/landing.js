/* ReCover landing page: language, switcher, hero slider, live data.
   Copy: window.RC_STRINGS (strings.js). No chat/swap logic here. */
(function () {
  "use strict";

  // Sourced: EPD NEPD-1805-759 (Helland Duun 3-seater sofa, 47.7 kg):
  // 52 kg CO2e for life-cycle stages A1-A3 (manufacturing).
  var CO2_PER_SOFA_KG = 52;

  // Real hero swap: living sample, 3-item multi (sofa + cushions +
  // curtains); caption names the sofa fabric, score is its verify min.
  var HERO = { code: "FA-AC-01", score: 9 };

  var RTL = ["ar", "ur", "fa"];

  function initialLang() {
    try {
      var saved = window.localStorage.getItem("recover_lang");
      if (saved && window.RC_STRINGS[saved]) return saved;
    } catch (e) {}
    var q = new URLSearchParams(location.search).get("lang");
    if (q && window.RC_STRINGS[q]) return q;
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

  function loadCaption() {
    fetch("/api/fabric/" + encodeURIComponent(HERO.code))
      .then(function (r) {
        if (!r.ok) throw new Error("fabric");
        return r.json();
      })
      .then(function (f) {
        var name = lang === "ar" ? f.name_ar : f.name_en;
        document.getElementById("capName").textContent = name || "";
        document.getElementById("capCode").textContent = f.code || "";
        document.getElementById("capSpecs").textContent =
          (f.material || "") + " · " + (f.price_sar_per_m || "") + " SAR/m";
        var img = document.getElementById("capImg");
        img.src = "/" + String(f.image || "").replace(/^\/+/, "");
        img.alt = name || "";
        document.getElementById("capBadge").textContent =
          t("verifiedBadge").replace("%d", HERO.score);
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
        document.getElementById("metEval").textContent =
          t("metEval").replace("%d", m.eval_pass)
            .replace("%d", m.eval_total);
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
    loadCaption();
    loadMetrics();
    icons();
  });
})();
