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
      thinkingNote: "Still thinking…",
      uploadFail: "Upload failed. Please try a JPG or PNG photo.",
      voiceFail: "Sorry, I couldn't hear that. Please try again.",
      micLabel: "Voice input",
      needPhoto: "Please upload a room photo first, then tap “See it in my space” again.",
      tailoring: "Tailoring your %s…",
      pieceWord: { sofa: "sofa", armchair: "armchair", curtains: "curtains", cushions: "cushions" },
      stepDetect: "Detecting piece",
      stepApply: "Applying fabric",
      stepCheck: "Checking match",
      stillWorking: "Still working — complex rooms take a few minutes.",
      matchBadge: "Fabric match %d/10",
      downloadLabel: "Download",
      closeLabel: "Close",
      swapFail: "The preview failed. Please try again with another photo.",
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
      thinkingNote: "لحظة، أفكر…",
      uploadFail: "فشل الرفع. جرب صورة JPG أو PNG.",
      voiceFail: "عذراً، ما سمعتك زين. حاول مرة ثانية.",
      micLabel: "إدخال صوتي",
      needPhoto: "ارفع صورة غرفتك أول، بعدين اضغط “شاهدها في مساحتك”.",
      tailoring: "نفصّل %s بقماشك…",
      pieceWord: { sofa: "الكنبة", armchair: "الكرسي", curtains: "الستائر", cushions: "الوسائد" },
      stepDetect: "نحدد القطعة",
      stepApply: "نركّب القماش",
      stepCheck: "نتأكد من التطابق",
      stillWorking: "لسه شغالين — الغرف المعقدة تأخذ كم دقيقة.",
      matchBadge: "تطابق القماش %d/10",
      downloadLabel: "تحميل",
      closeLabel: "إغلاق",
      swapFail: "تعذّرت المعاينة. حاول مرة ثانية بصورة ثانية.",
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
    booted: false,
    roomPhoto: null,
    detectedPiece: null
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
    $("micBtn").setAttribute("aria-label", t("micLabel"));
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

  var MIC_BADGE = '<span class="voice-badge" aria-hidden="true"><svg viewBox="0 0 24 24" width="13" height="13"><path fill="currentColor" d="M12 2a3 3 0 013 3v6a3 3 0 01-6 0V5a3 3 0 013-3zm7 10a7 7 0 01-14 0H3a9 9 0 008 8.9V22h2v-1.1A9 9 0 0021 12h-2z"/></svg></span>';

  function formatReply(text) {
    return esc(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function addMsg(text, who, photo, voice) {
    var div = document.createElement("div");
    div.className = "msg " + who;
    if (who === "them") {
      var av = document.createElement("span");
      av.className = "avatar";
      av.textContent = "R";
      div.appendChild(av);
    }
    var body = document.createElement("div");
    body.innerHTML = (voice ? MIC_BADGE : "") + formatReply(text);
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

  function fetchReq(url, opts) {
    var timeoutMs = (opts && opts.timeoutMs) || 60000;
    var retries = (opts && typeof opts.retries === "number") ? opts.retries : 1;
    var attempt = 0;
    function once() {
      attempt += 1;
      var ctrl = null, timer = null;
      if (typeof AbortController !== "undefined") {
        ctrl = new AbortController();
        timer = setTimeout(function () { ctrl.abort(); }, timeoutMs);
      }
      var init = { method: "POST" };
      if (ctrl) init.signal = ctrl.signal;
      if (opts && opts.json !== undefined) {
        init.headers = { "Content-Type": "application/json" };
        init.body = JSON.stringify(opts.json);
      } else if (opts && opts.form) {
        init.body = opts.form;
      }
      return fetch(url, init).then(function (r) {
        if (timer) clearTimeout(timer);
        if (!r.ok) {
          var err = new Error("HTTP " + r.status);
          err.http = true;
          throw err;
        }
        return r.json();
      }).catch(function (e) {
        if (timer) clearTimeout(timer);
        if (e && e.http) throw e;
        if (attempt <= retries) return once();
        throw new Error("request failed");
      });
    }
    return once();
  }

  function postJSON(url, payload, timeoutMs, retries) {
    return fetchReq(url, { json: payload, timeoutMs: timeoutMs,
                           retries: retries });
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
        '<button class="seeit" type="button" data-code="' + esc(r.code) + '">' + esc(t("seeIt")) + "</button>" +
        "</div>";
      recsEl.appendChild(card);
    });
  }

  function handleResult(res) {
    renderRoomCard(res.room_analysis, res.detected_piece);
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    if (res.reply) addMsg(res.reply, "them");
    if (res.recommendations && res.recommendations.length) renderRecs(res.recommendations);
  }

  function swapTarget() {
    var piece = (state.detectedPiece || "").toLowerCase();
    if (piece.indexOf("chair") >= 0) return "armchair";
    if (piece.indexOf("curtain") >= 0 || piece.indexOf("drape") >= 0 ||
        piece.indexOf("ستائر") >= 0 || piece.indexOf("ستارة") >= 0) return "curtains";
    if (piece.indexOf("cushion") >= 0 || piece.indexOf("pillow") >= 0 ||
        piece.indexOf("وسا") >= 0 || piece.indexOf("مخد") >= 0) return "cushions";
    return "sofa";
  }

  var swapTimers = [];

  function clearSwapTimers() {
    swapTimers.forEach(clearTimeout);
    swapTimers = [];
  }

  function setStep(n) {
    var items = document.querySelectorAll("#swapSteps li");
    for (var i = 0; i < items.length; i++) {
      items[i].className = i < n ? "done" : i === n ? "active" : "";
    }
  }

  function openSwap(code) {
    if (!state.roomPhoto) {
      addMsg(t("needPhoto"), "them");
      var dz = $("dropzone");
      dz.scrollIntoView({ behavior: "smooth", block: "center" });
      dz.classList.add("flash");
      setTimeout(function () { dz.classList.remove("flash"); }, 1600);
      return;
    }
    var target = swapTarget();
    var words = t("pieceWord") || {};
    $("swapTitle").textContent =
      t("tailoring").replace("%s", words[target] || target);
    $("swapLoading").hidden = false;
    $("swapResult").hidden = true;
    $("swapStill").hidden = true;
    $("swapModal").hidden = false;
    document.body.classList.add("modal-open");
    setStep(0);
    clearSwapTimers();
    swapTimers.push(setTimeout(function () { setStep(1); }, 25000));
    swapTimers.push(setTimeout(function () { setStep(2); }, 100000));
    swapTimers.push(setTimeout(function () {
      $("swapStill").hidden = false;
      setStep(2);
    }, 180000));
    fetchReq("/api/swap", {
      json: { session_id: state.sessionId,
              image_path: state.roomPhoto,
              fabric_code: code, target: target },
      timeoutMs: 600000, retries: 0
    }).then(function (res) {
      clearSwapTimers();
      var scores = res.scores || {};
      var vals = [scores.color, scores.pattern, scores.scale,
                  scores.isolation].map(function (v) { return v || 0; });
      var match = Math.min.apply(null, vals);
      var before = "/" + state.roomPhoto.replace(/^\/+/, "");
      var after = "/" + (res.result_url || "").replace(/^\/+/, "");
      $("baBeforeImg").src = before;
      $("baAfterImg").src = after;
      $("baRange").value = 50;
      baUpdate(50);
      var badge = $("matchBadge");
      badge.textContent = t("matchBadge").replace("%d", match);
      badge.title = "color " + vals[0] + " · pattern " + vals[1] +
                    " · scale " + vals[2] + " · isolation " + vals[3];
      var dl = $("swapDownload");
      dl.href = after;
      dl.textContent = t("downloadLabel");
      $("swapLoading").hidden = true;
      $("swapResult").hidden = false;
    }).catch(function () {
      clearSwapTimers();
      closeSwap();
      addMsg(t("swapFail"), "them");
    });
  }

  function baUpdate(pct) {
    $("baBefore").style.clipPath =
      "inset(0 " + (100 - pct) + "% 0 0)";
    $("baHandle").style.left = pct + "%";
  }

  function closeSwap() {
    clearSwapTimers();
    $("swapModal").hidden = true;
    document.body.classList.remove("modal-open");
  }

  function streamChat(text, imagePath) {
    return new Promise(function (resolve, reject) {
      var ctrl = new AbortController();
      var settled = false, stall = null;
      var bubble = null, bodyEl = null, raw = "";
      function armStall() {
        if (stall) clearTimeout(stall);
        stall = setTimeout(function () {
          try { ctrl.abort(); } catch (e) {}
          finish(new Error("stall"));
        }, 75000);
      }
      function finish(err, res) {
        if (settled) return;
        settled = true;
        if (stall) clearTimeout(stall);
        if (err) reject(err);
        else resolve(res);
      }
      function ensureBubble() {
        if (bubble) return;
        bubble = addMsg("", "them");
        bodyEl = bubble.lastElementChild;
        bodyEl.textContent = "";
      }
      fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: text || "",
          image_path: imagePath || null
        }),
        signal: ctrl.signal
      }).then(function (r) {
        if (!r.ok || !r.body) throw new Error("HTTP " + r.status);
        armStall();
        var reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function onEvt(evt) {
          if (evt.type === "token") {
            ensureBubble();
            raw += evt.text;
            bodyEl.textContent = raw;
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (evt.type === "done") {
            if (bodyEl) bodyEl.innerHTML = formatReply(raw);
            else if (evt.result && evt.result.reply) {
              addMsg(evt.result.reply, "them");
            }
            try { reader.cancel(); } catch (e) {}
            finish(null, evt.result);
          } else if (evt.type === "error") {
            try { reader.cancel(); } catch (e) {}
            finish(new Error("srv"));
          }
        }
        function pump() {
          return reader.read().then(function (step) {
            if (step.done) { finish(new Error("closed")); return; }
            armStall();
            buf += dec.decode(step.value, { stream: true });
            var parts = buf.split("\n\n");
            buf = parts.pop();
            parts.forEach(function (part) {
              part.split("\n").forEach(function (line) {
                line = line.trim();
                if (line.indexOf("data:") !== 0) return;
                try { onEvt(JSON.parse(line.slice(5))); }
                catch (e) {}
              });
            });
            if (!settled) return pump();
          });
        }
        return pump();
      }).catch(function (e) {
        if (bubble || raw) { finish(e); return; }
        postJSON("/api/chat", {
          session_id: state.sessionId,
          message: text || "",
          image_path: imagePath || null
        }, 120000, 1).then(function (res) {
          res.fallback = true;
          finish(null, res);
        }).catch(finish);
      });
    });
  }

  function send(text, imagePath, photoPreview) {
    if (!text && !imagePath) return;
    addMsg(text || "", "me", photoPreview);
    typingOn();
    var thinkingTimer = setTimeout(function () {
      var el = document.createElement("div");
      el.className = "msg them";
      el.id = "thinking";
      el.innerHTML = '<span class="avatar">R</span><div><i>' +
        esc(t("thinkingNote")) + "</i></div>";
      messagesEl.appendChild(el);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }, 8000);
    function finish() {
      clearTimeout(thinkingTimer);
      var th = document.getElementById("thinking");
      if (th) th.remove();
      typingOff();
    }
    streamChat(text, imagePath).then(function (res) {
      finish();
      if (!res) return;
      if (res.fallback && res.reply) addMsg(res.reply, "them");
      handleStreamResult(res);
    }).catch(function () {
      finish();
      addMsg(t("sendFail"), "them");
    });
  }

  function handleStreamResult(res) {
    renderRoomCard(res.room_analysis, res.detected_piece);
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    if (res.recommendations && res.recommendations.length) {
      renderRecs(res.recommendations);
    }
  }

  function upload(file) {
    var fd = new FormData();
    fd.append("file", file);
    var preview = URL.createObjectURL(file);
    addMsg("", "me", preview);
    var note = addMsg(t("analyzing"), "them");
    fetchReq("/api/upload", { form: fd, timeoutMs: 60000, retries: 1 })
      .then(function (data) {
        note.remove();
        state.roomPhoto = data.image_path;
        typingOn();
        return postJSON("/api/chat", {
          session_id: state.sessionId,
          message: "",
          image_path: data.image_path
        }, 120000, 1);
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

  var recorder = null, recChunks = [], recStart = 0, recTick = null;

  function fmtTime(ms) {
    var s = Math.floor(ms / 1000);
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  function setRecording(on) {
    var btn = $("micBtn"), ui = $("recUI");
    btn.classList.toggle("recording", on);
    ui.hidden = !on;
    if (on) {
      recStart = Date.now();
      $("recTimer").textContent = "0:00";
      recTick = setInterval(function () {
        $("recTimer").textContent = fmtTime(Date.now() - recStart);
      }, 250);
    } else {
      clearInterval(recTick);
      recTick = null;
    }
  }

  function sendVoice(blob) {
    var ext = (blob.type || "").indexOf("mp4") >= 0 ? ".m4a" : ".webm";
    var fd = new FormData();
    fd.append("file", blob, "recording" + ext);
    typingOn();
    fetchReq("/api/voice", { form: fd, timeoutMs: 180000, retries: 1 })
      .then(function (data) {
        typingOff();
        chipsEl.hidden = true;
        state.booted = true;
        addMsg(data.text, "me", null, true);
        send(data.text);
      })
      .catch(function () {
        typingOff();
        addMsg(t("voiceFail"), "them");
      });
  }

  function setupVoice() {
    var btn = $("micBtn");
    btn.setAttribute("aria-label", t("micLabel"));
    btn.addEventListener("click", function () {
      if (recorder) {
        recorder.stop();
        return;
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia ||
          typeof MediaRecorder === "undefined") {
        addMsg(t("voiceFail"), "them");
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        recChunks = [];
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = function (e) {
          if (e.data && e.data.size) recChunks.push(e.data);
        };
        recorder.onstop = function () {
          var tracks = stream.getTracks();
          tracks.forEach(function (tr) { tr.stop(); });
          setRecording(false);
          var rec = recorder;
          recorder = null;
          if (recChunks.length) sendVoice(new Blob(recChunks, { type: rec.mimeType }));
        };
        recorder.start();
        setRecording(true);
      }).catch(function () {
        addMsg(t("voiceFail"), "them");
      });
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

    setupVoice();

    recsEl.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".seeit") : null;
      if (btn && btn.dataset.code) openSwap(btn.dataset.code);
    });
    $("baRange").addEventListener("input", function (e) {
      baUpdate(Number(e.target.value));
    });
    $("swapClose").addEventListener("click", closeSwap);
    $("swapModal").addEventListener("click", function (e) {
      if (e.target === $("swapModal")) closeSwap();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("swapModal").hidden) closeSwap();
    });

    typingOn();
    postJSON("/api/chat", {
      session_id: state.sessionId,
      message: state.lang === "ar" ? "مرحبا" : "Hello"
    }, 60000, 1)
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
