/* ReCover chat UI. No build step, vanilla JS. */
(function () {
  "use strict";

  var STRINGS = {
    en: {
      tagline: "Change the look, not the furniture.",
      forYou: "For you",
      emptyRecs: "Your recommended fabrics will appear here.",
      dropHint: "Drop a room photo here, or tap to choose one",
      placeholder: "Ask about fabrics…",
      analyzing: "Analyzing your room…",
      seeIt: "See it in my space",
      comingSoon: "Coming soon",
      perMeter: "SAR/m",
      matchSection: "Why this fabric",
      relaxSection: "Adjusted for you",
      sendFail: "Sorry, something went wrong. Please try again.",
      uploadFail: "Upload failed. Please try a JPG or PNG photo.",
      roomTitle: "Your room",
      roomType: "Room",
      style: "Style",
      light: "Light",
      piece: "Piece",
      palette: "Wall palette",
      chips: ["Upholstery", "Curtains", "Cushions", "A mix"],
      snag: { low: "Low snag risk", medium: "Medium snag risk", high: "High snag risk", unknown: "Snag risk n/a" },
      features: {},
      matched: {},
      relaxed: {}
    },
    ar: {
      tagline: "غيّر القماش، لا الأثاث.",
      forYou: "اخترنا لك",
      emptyRecs: "ستظهر أقمشتك المقترحة هنا.",
      dropHint: "أسقط صورة غرفتك هنا، أو اضغط لاختيار صورة",
      placeholder: "اسأل عن الأقمشة…",
      analyzing: "جارٍ تحليل غرفتك…",
      seeIt: "شاهدها في مساحتك",
      comingSoon: "قريباً",
      perMeter: "ر.س/م",
      matchSection: "لماذا هذا القماش",
      relaxSection: "عدّلنا لك",
      sendFail: "عذراً، حدث خطأ. حاول مرة أخرى.",
      uploadFail: "فشل الرفع. جرب صورة JPG أو PNG.",
      roomTitle: "غرفتك",
      roomType: "الغرفة",
      style: "الستايل",
      light: "الإضاءة",
      piece: "القطعة",
      palette: "ألوان الجدران",
      chips: ["تنجيد", "ستائر", "وسائد", "تشكيلة"],
      snag: { low: "مقاومة عالية للتشابك", medium: "مقاومة متوسطة للتشابك", high: "عرضة للتشابك", unknown: "غير معروف" },
      features: {},
      matched: {},
      relaxed: {}
    }
  };

  var FEATURE_LABELS = {
    "fire-resistant": ["Fire-resistant", "مقاوم للحريق"],
    "easy-clean": ["Easy-clean", "سهل التنظيف"],
    "washable": ["Washable", "قابل للغسل"],
    "stain-resistant": ["Stain-resistant", "مقاوم للبقع"],
    "antibacterial": ["Antibacterial", "مضاد للبكتيريا"],
    "pet-friendly": ["Pet-friendly", "مناسب للحيوانات"],
    "scratch-resistant": ["Scratch-resistant", "مقاوم للخدش"],
    "fade-resistant": ["Fade-resistant", "مقاوم للبهتان"],
    "crease-resistant": ["Crease-resistant", "مقاوم للتجعد"],
    "blackout": ["Blackout", "تعتيم كامل"],
    "thermal-insulating": ["Thermal", "عازل حراري"],
    "sound-absorbing": ["Sound-absorbing", "ماص للصوت"],
    "hypoallergenic": ["Hypoallergenic", "مضاد للحساسية"],
    "eco-friendly": ["Eco-friendly", "صديق للبيئة"],
    "under-budget": ["Under budget", "ضمن الميزانية"],
    "warm-tone": ["Warm tone", "درجة دافئة"],
    "cool-tone": ["Cool tone", "درجة باردة"],
    "neutral-tone": ["Neutral tone", "درجة محايدة"]
  };

  var RELAX_LABELS = {
    "max_price": ["Budget", "الميزانية"],
    "features": ["Fabric features", "مواصفات القماش"],
    "any_features": ["Pet protection", "الحماية من الحيوانات"],
    "snag_levels": ["Claw-safe weave", "قماش آمن من الخدش"],
    "min_martindale": ["Durability", "المتانة"],
    "colors": ["Colors", "الألوان"],
    "tone": ["Color tone", "درجة اللون"],
    "styles": ["Style", "الستايل"],
    "suitable_for": ["Intended use", "الاستخدام المقصود"],
    "plain_or_patterned": ["Pattern", "النقشة"],
    "opacity": ["Curtain opacity", "تعتيم الستارة"],
    "usage": ["Fabric use", "استخدام القماش"]
  };

  var state = {
    lang: (new URLSearchParams(location.search).get("lang") === "ar") ? "ar" : "en",
    sessionId: "web-" + Math.random().toString(36).slice(2, 10),
    booted: false
  };

  var $ = function (id) { return document.getElementById(id); };
  var messagesEl, chipsEl, recsEl, roomCardEl, composerInput;

  function t(key) { return STRINGS[state.lang][key]; }

  function featLabel(key) {
    var pair = FEATURE_LABELS[key] || [key, key];
    return state.lang === "ar" ? pair[1] : pair[0];
  }

  function relaxLabel(key) {
    var pair = RELAX_LABELS[key] || [key, key];
    return state.lang === "ar" ? pair[1] : pair[0];
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.documentElement.dir = state.lang === "ar" ? "rtl" : "ltr";
    document.body.classList.toggle("ar", state.lang === "ar");
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
    });
    $("langToggle").textContent = state.lang === "ar" ? "EN" : "عربي";
    renderChips();
  }

  function renderChips() {
    chipsEl.innerHTML = "";
    t("chips").forEach(function (label) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.addEventListener("click", function () {
        chipsEl.hidden = true;
        send(label);
      });
      chipsEl.appendChild(b);
    });
    if (!state.booted) chipsEl.hidden = false;
  }

  function addMsg(text, who, photo) {
    var div = document.createElement("div");
    div.className = "msg " + who;
    if (who === "them") {
      var av = document.createElement("span");
      av.className = "avatar";
      av.textContent = "R";
      div.appendChild(av);
    }
    var body = document.createElement("div");
    body.innerHTML = esc(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
    if (photo) {
      var img = document.createElement("img");
      img.className = "chat-photo";
      img.src = photo;
      img.alt = "uploaded room";
      body.appendChild(img);
    }
    div.appendChild(body);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function typingOn() {
    var div = document.createElement("div");
    div.className = "msg them";
    div.id = "typing";
    div.innerHTML = '<span class="avatar">R</span><span class="typing"><span></span><span></span><span></span></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function typingOff() {
    var el = document.getElementById("typing");
    if (el) el.remove();
  }

  function postJSON(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function snagClass(level) {
    return level === "low" ? "snag-low" : level === "medium" ? "snag-medium" : "snag-high";
  }

  function renderRoomCard(room, detectedPiece) {
    if (!room) { roomCardEl.hidden = true; return; }
    var rows = "";
    rows += "<div><b>" + esc(t("roomType")) + ":</b> " + esc(room.room_type || "—") + "</div>";
    rows += "<div><b>" + esc(t("style")) + ":</b> " + esc(room.style || "—") + "</div>";
    rows += "<div><b>" + esc(t("light")) + ":</b> " + esc(room.light_level || "—") + "</div>";
    var piece = detectedPiece || (room.furniture || "").split(",")[0];
    rows += "<div><b>" + esc(t("piece")) + ":</b> " + esc(piece || "—") + "</div>";
    var pal = "";
    (room.wall_colors || []).forEach(function (c) {
      pal += '<span class="swatch-chip" title="' + esc(c.name + " " + c.hex) +
        '" style="background:' + esc(c.hex) + '"></span>';
    });
    roomCardEl.innerHTML = "<h3>" + esc(t("roomTitle")) + "</h3>" + rows +
      '<div><b>' + esc(t("palette")) + ":</b></div>" +
      '<div class="palette">' + pal + "</div>";
    roomCardEl.hidden = false;
  }

  function renderRecs(recs) {
    recsEl.innerHTML = "";
    if (!recs || !recs.length) {
      var p = document.createElement("p");
      p.className = "empty";
      p.textContent = t("emptyRecs");
      recsEl.appendChild(p);
      return;
    }
    recs.forEach(function (r) {
      var card = document.createElement("div");
      card.className = "card";
      var name = state.lang === "ar" ? r.name_ar : r.name_en;
      var feats = (r.features || []).map(function (f) {
        return '<span class="tag">' + esc(featLabel(f)) + "</span>";
      }).join("");
      var matched = (r.matched || []).map(function (m) {
        return '<li><span class="yes">✓</span> ' + esc(featLabel(m)) + "</li>";
      }).join("");
      var relaxed = (r.relaxed || []).map(function (m) {
        return '<li><span class="warn">⚠</span> ' + esc(relaxLabel(m)) + "</li>";
      }).join("");
      var receipts = "";
      if (matched || relaxed) {
        receipts = '<ul class="receipts">' + matched + relaxed + "</ul>";
      }
      card.innerHTML =
        '<div class="swatch"><img src="/' + esc(r.image) + '" alt="' + esc(name) + '" loading="lazy"></div>' +
        '<div class="body">' +
        '<div class="name">' + esc(name) + "</div>" +
        '<div class="meta">' + esc(r.code) + " · " + esc(r.price_sar_per_m) + " " + esc(t("perMeter")) + "</div>" +
        '<div class="tagrow">' + feats +
        '<span class="tag ' + snagClass(r.snag_risk) + '">' + esc(t("snag")[r.snag_risk] || r.snag_risk) + "</span></div>" +
        (r.reason ? '<p class="why">' + esc(r.reason) + "</p>" : "") +
        receipts +
        '<button class="seeit" type="button" disabled title="' + esc(t("comingSoon")) + '">' + esc(t("seeIt")) + "</button>" +
        "</div>";
      recsEl.appendChild(card);
    });
  }

  function handleResult(res) {
    renderRoomCard(res.room_analysis, res.detected_piece);
    if (res.reply) addMsg(res.reply, "them");
    if (res.recommendations && res.recommendations.length) renderRecs(res.recommendations);
  }

  function send(text, imagePath, photoPreview) {
    if (!text && !imagePath) return;
    addMsg(text || "", "me", photoPreview);
    typingOn();
    postJSON("/api/chat", {
      session_id: state.sessionId,
      message: text || "",
      image_path: imagePath || null
    }).then(function (res) {
      typingOff();
      handleResult(res);
    }).catch(function () {
      typingOff();
      addMsg(t("sendFail"), "them");
    });
  }

  function upload(file) {
    var fd = new FormData();
    fd.append("file", file);
    var preview = URL.createObjectURL(file);
    addMsg("", "me", preview);
    var note = addMsg(t("analyzing"), "them");
    fetch("/api/upload", { method: "POST", body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error("upload");
        return r.json();
      })
      .then(function (data) {
        note.remove();
        typingOn();
        return postJSON("/api/chat", {
          session_id: state.sessionId,
          message: "",
          image_path: data.image_path
        });
      })
      .then(function (res) {
        typingOff();
        handleResult(res);
      })
      .catch(function () {
        typingOff();
        note.remove();
        addMsg(t("uploadFail"), "them");
      });
  }

  function boot() {
    messagesEl = $("messages");
    chipsEl = $("chips");
    recsEl = $("recs");
    roomCardEl = $("roomCard");
    composerInput = $("composerInput");

    applyI18n();

    $("langToggle").addEventListener("click", function () {
      state.lang = state.lang === "ar" ? "en" : "ar";
      applyI18n();
    });

    $("composer").addEventListener("submit", function (e) {
      e.preventDefault();
      var text = composerInput.value.trim();
      if (!text) return;
      composerInput.value = "";
      chipsEl.hidden = true;
      state.booted = true;
      send(text);
    });

    var dz = $("dropzone");
    var fi = $("fileInput");
    dz.addEventListener("click", function () { fi.click(); });
    dz.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") fi.click();
    });
    fi.addEventListener("change", function () {
      if (fi.files[0]) upload(fi.files[0]);
      fi.value = "";
    });
    ["dragover", "dragenter"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("over"); });
    });
    dz.addEventListener("drop", function (e) {
      if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    });

    typingOn();
    postJSON("/api/chat", {
      session_id: state.sessionId,
      message: state.lang === "ar" ? "مرحبا" : "Hello"
    })
      .then(function (res) {
        typingOff();
        handleResult(res);
        chipsEl.hidden = false;
      })
      .catch(function () {
        typingOff();
        addMsg(t("sendFail"), "them");
      });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
