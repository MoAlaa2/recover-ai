/* Designer mode: floor plan -> numbered pieces -> fabrics -> top-down
   concept render -> client proposal PDF. Meta models only (Spark lists
   the pieces, muse-image-1.0 renders). No chat here. */
(function () {
  "use strict";

  var STRINGS = {
    en: {
      crumbHome: "Home", crumbDesigner: "Designer mode",
      toConsult: "Consultation",
      dropPlan: "Drop a floor plan (PNG, JPG or PDF)",
      uploadPlan: "Upload plan",
      planHint: "Muse Spark finds the upholstered pieces; you fix the boxes, pick fabrics, and render a top-down concept.",
      stepPieces: "Pieces", stepFabrics: "Fabrics", stepRender: "Render",
      dragHint: "Drag a box to move it, pull its corner to resize, or remove a wrong piece.",
      fabricHint: "Tap a piece's fabric to choose from the catalog.",
      refind: "Find pieces again",
      renderBtn: "Render concept",
      renderHint: "muse-image-1.0 · about 30 seconds · colour-checked per piece",
      rendering: "Rendering your concept…",
      stepEdit: "Painting the fabrics", stepCheck: "Checking each piece",
      stepRetry: "Refining the colours",
      notToScale: "Concept render — not to scale",
      preparedBy: "Prepared by (optional)",
      downloadLabel: "Download", proposalPdf: "Client proposal (PDF)",
      closeLabel: "Close",
      uploading: "Reading your plan…", finding: "Finding the pieces…",
      found: "%d piece(s) found · Spark",
      noPieces: "No upholstered pieces found. Try a clearer plan.",
      chooseFabric: "Choose fabric", browseTitle: "Pick a fabric",
      closeBrowse: "Close", applyOne: "Use this",
      piece: "Piece", removed: "Removed",
      uploadFail: "Could not read that plan.",
      renderFail: "Sorry, the render failed. Try again.",
      checkOk: "colour ✓", checkBad: "colour ✗",
      totalLabel: "Total", preliminaryNote: "Preliminary estimate — your upholsterer will measure.",
      co2Line: "By keeping these pieces you avoid ≈%d kg CO₂e of new manufacturing and ≈%d kg of furniture waste",
      co2Source: "Source: EPD NEPD-1805-759",
      meters: "%s m", sarPerM: "%s SAR/m", sar: "%s SAR",
      pdfBusy: "Preparing the PDF…", pdfFail: "Could not build the PDF.",
      pdfDone: "PDF ready — check your downloads.",
      sendFail: "Could not reach ReCover. Try again.",
      types: { "sofa-3-seat": "Sofa", "loveseat": "Loveseat", "sectional": "Sectional", "armchair": "Armchair", "wingback": "Wingback", "ottoman": "Ottoman", "sofa-2-seat": "Daybed" }
    },
    ar: {
      crumbHome: "الرئيسية", crumbDesigner: "وضع المصمم",
      toConsult: "الاستشارة",
      dropPlan: "اسحب مخطط الغرفة هنا (PNG أو JPG أو PDF)",
      uploadPlan: "ارفع المخطط",
      planHint: "Muse Spark يحدد القطع المنجّدة، وأنت تضبط المربعات وتختار الأقمشة ثم تولّد تصورًا علويًا.",
      stepPieces: "القطع", stepFabrics: "الأقمشة", stepRender: "التصور",
      dragHint: "اسحب المربع لتحريكه، أو اسحب زاويته لتغيير حجمه، أو احذف قطعة خاطئة.",
      fabricHint: "اضغط على قماش القطعة لتختار من الكتالوج.",
      refind: "أعد البحث عن القطع",
      renderBtn: "ولّد التصور",
      renderHint: "muse-image-1.0 · نحو ٣٠ ثانية · فحص لون لكل قطعة",
      rendering: "نجهّز التصور…",
      stepEdit: "نكسو القطع بالقماش", stepCheck: "نفحص كل قطعة",
      stepRetry: "نضبط الألوان",
      notToScale: "تصور مبدئي — ليس بمقياس الرسم",
      preparedBy: "إعداد (اختياري)",
      downloadLabel: "تنزيل", proposalPdf: "عرض للعميل (PDF)",
      closeLabel: "إغلاق",
      uploading: "نقرأ المخطط…", finding: "نبحث عن القطع…",
      found: "وجدنا %d قطعة · Spark",
      noPieces: "لم نجد قطعًا منجّدة. جرّب مخططًا أوضح.",
      chooseFabric: "اختر القماش", browseTitle: "اختر قماشًا",
      closeBrowse: "إغلاق", applyOne: "اختر هذا",
      piece: "قطعة", removed: "حُذفت",
      uploadFail: "تعذّر قراءة هذا المخطط.",
      renderFail: "عذرًا، فشل التصور. حاول مرة أخرى.",
      checkOk: "اللون ✓", checkBad: "اللون ✗",
      totalLabel: "الإجمالي", preliminaryNote: "تقدير مبدئي — المقاس النهائي من المنجّد.",
      co2Line: "باحفاظك على هذه القطع تتجنّب ≈%d كغ CO₂e من التصنيع الجديد و≈%d كغ من نفايات الأثاث",
      co2Source: "المصدر: EPD NEPD-1805-759",
      meters: "%s م", sarPerM: "%s ر.س/م", sar: "%s ر.س",
      pdfBusy: "نجهّز ملف PDF…", pdfFail: "تعذّر إنشاء الملف.",
      pdfDone: "الملف جاهز — راجع التنزيلات.",
      sendFail: "تعذّر الوصول إلى ReCover. حاول مرة أخرى.",
      types: { "sofa-3-seat": "كنبة", "loveseat": "كنبة مقعدين", "sectional": "كنبة زاوية", "armchair": "كرسي", "wingback": "كرسي بأذنين", "ottoman": "مقعد صغير", "sofa-2-seat": "كنبة" }
    }
  };

  var state = {
    lang: "en", plan: null, pieces: [], sel: null, browseFor: null,
    browseList: [], render: null, busy: false
  };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function t(key) {
    var pack = STRINGS[state.lang] || STRINGS.en;
    return pack[key] !== undefined ? pack[key] : STRINGS.en[key];
  }
  function toArabicDigits(text) {
    return String(text).replace(/[0-9]/g, function (d) {
      return "٠١٢٣٤٥٦٧٨٩"[+d];
    });
  }
  function num(n, dec) {
    if (n === undefined || n === null) return "—";
    var v = Number(n);
    var s = (dec === 0 || Math.abs(v - Math.round(v)) < 0.005) ?
      String(Math.round(v)) : v.toFixed(dec === undefined ? 1 : dec);
    return state.lang === "ar" ? toArabicDigits(s) : s;
  }
  function fmt(key, value) { return t(key).replace("%s", value); }
  function typeLabel(type) {
    var m = t("types") || {};
    return m[type] || STRINGS.en.types[type] || type;
  }
  function icons() { if (window.lucide) window.lucide.createIcons(); }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.documentElement.dir = state.lang === "ar" ? "rtl" : "ltr";
    document.body.classList.toggle("ar", state.lang === "ar");
    Array.prototype.forEach.call(document.querySelectorAll("[data-i18n]"),
      function (el) {
        var v = t(el.getAttribute("data-i18n"));
        if (v !== undefined) el.textContent = v;
      });
    renderList();
    renderBoxes();
    if (state.render) renderResult(state.render);
    if (window.RCSwitcher) window.RCSwitcher.refresh();
  }

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && STRINGS[q]) return q;
    try {
      var saved = window.localStorage.getItem("recover_lang");
      if (saved && STRINGS[saved]) return saved;
      if (saved) return "en";
    } catch (e) {}
    var nav = (navigator.language || "en").toLowerCase();
    return nav.indexOf("ar") === 0 ? "ar" : "en";
  }

  function setLang(code) {
    state.lang = STRINGS[code] ? code : "en";
    try { window.localStorage.setItem("recover_lang", code); } catch (e) {}
    applyI18n();
  }

  function status(text, show) {
    var el = $("dzStatus");
    el.textContent = text || "";
    el.hidden = !show;
  }

  // ---- plan upload ----------------------------------------------------

  function uploadPlan(file) {
    if (!file || state.busy) return;
    state.busy = true;
    status(t("uploading"), true);
    var fd = new FormData();
    fd.append("file", file, file.name || "plan.png");
    fetch("/api/designer/plan", { method: "POST", body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error("upload");
        return r.json();
      })
      .then(function (data) {
        state.plan = data;
        state.pieces = [];
        state.render = null;
        state.sel = null;
        $("dzEmpty").hidden = true;
        $("dzPlanWrap").hidden = false;
        $("dzPlanImg").src = "/" + data.image_path.replace(/^\/+/, "");
        $("dzRefind").hidden = false;
        renderList();
        renderBoxes();
        return findPieces();
      })
      .catch(function () {
        status(t("uploadFail"), true);
      })
      .then(function () { state.busy = false; updateRenderBtn(); });
  }

  function findPieces() {
    if (!state.plan) return Promise.resolve();
    status(t("finding"), true);
    return fetch("/api/designer/pieces", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_path: state.plan.image_path })
    }).then(function (r) {
      if (!r.ok) throw new Error("pieces");
      return r.json();
    }).then(function (data) {
      state.pieces = (data.pieces || []).map(function (p) {
        return { id: p.id, name: p.name, type: p.type, box: p.box.slice(),
                 code: null, meta: null };
      });
      status(state.pieces.length ?
        t("found").replace("%d", num(state.pieces.length, 0)) :
        t("noPieces"), true);
      renderList();
      renderBoxes();
      updateRenderBtn();
    }).catch(function () {
      status(t("sendFail"), true);
    });
  }

  // ---- boxes (numbered outlines, drag / resize) ----------------------

  function clampBox(b) {
    var W = state.plan.width, H = state.plan.height;
    var minW = Math.max(4, W * 0.01), minH = Math.max(4, H * 0.01);
    var x1 = Math.max(0, Math.min(W - minW, b[0]));
    var y1 = Math.max(0, Math.min(H - minH, b[1]));
    var x2 = Math.max(x1 + minW, Math.min(W, b[2]));
    var y2 = Math.max(y1 + minH, Math.min(H, b[3]));
    return [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)];
  }

  function renderBoxes() {
    var layer = $("dzBoxes");
    if (!layer || !state.plan) return;
    var W = state.plan.width, H = state.plan.height;
    layer.innerHTML = state.pieces.map(function (p) {
      var b = p.box;
      return '<div class="dz-box' + (p.code ? " assigned" : "") +
        (state.sel === p.id ? " sel" : "") + '" data-id="' + p.id +
        '" style="left:' + (b[0] / W * 100) + "%;top:" + (b[1] / H * 100) +
        "%;width:" + ((b[2] - b[0]) / W * 100) + "%;height:" +
        ((b[3] - b[1]) / H * 100) + '%" title="' + esc(p.name) + '">' +
        '<span class="dz-num">' + num(p.id, 0) + "</span>" +
        '<span class="dz-handle" data-handle="1"></span></div>';
    }).join("");
  }

  function bindDrag() {
    var layer = $("dzBoxes");
    var drag = null;
    layer.addEventListener("pointerdown", function (e) {
      var box = e.target.closest(".dz-box");
      if (!box || !state.plan || drag) return;
      var id = +box.dataset.id;
      var piece = state.pieces.filter(function (p) { return p.id === id; })[0];
      if (!piece) return;
      e.preventDefault();
      state.sel = id;
      renderList();
      renderBoxes();
      var img = $("dzPlanImg");
      drag = { id: id, resize: !!e.target.closest("[data-handle]"),
               x: e.clientX, y: e.clientY, box: piece.box.slice(),
               scale: state.plan.width / Math.max(1, img.clientWidth) };
      try { layer.setPointerCapture(e.pointerId); } catch (err) {}
    });
    layer.addEventListener("pointermove", function (e) {
      if (!drag) return;
      var piece = state.pieces.filter(function (p) { return p.id === drag.id; })[0];
      if (!piece) return;
      var dx = (e.clientX - drag.x) * drag.scale;
      var dy = (e.clientY - drag.y) * drag.scale;
      var b = drag.box;
      if (drag.resize) {
        piece.box = clampBox([b[0], b[1], b[2] + dx, b[3] + dy]);
      } else {
        piece.box = clampBox([b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy]);
      }
      renderBoxes();
    });
    function end() {
      if (!drag) return;
      drag = null;
      renderList();
    }
    layer.addEventListener("pointerup", end);
    layer.addEventListener("pointercancel", end);
    // Touch fallback (browsers that send touch events without pointer
    // events, and emulators): same maths, first finger only.
    function touchPoint(e) { return e.touches && e.touches[0]; }
    layer.addEventListener("touchstart", function (e) {
      var tp = touchPoint(e);
      var box = tp && document.elementFromPoint(tp.clientX, tp.clientY);
      box = box && box.closest ? box.closest(".dz-box") : null;
      if (!box || drag || !state.plan) return;
      var id = +box.dataset.id;
      var piece = state.pieces.filter(function (p) { return p.id === id; })[0];
      if (!piece) return;
      var onHandle = document.elementFromPoint(tp.clientX, tp.clientY);
      drag = { id: id, resize: !!(onHandle && onHandle.closest("[data-handle]")),
               x: tp.clientX, y: tp.clientY, box: piece.box.slice(),
               scale: state.plan.width / Math.max(1, $("dzPlanImg").clientWidth),
               touch: true };
      state.sel = id;
      renderList();
      renderBoxes();
      e.preventDefault();
    }, { passive: false });
    layer.addEventListener("touchmove", function (e) {
      if (!drag || !drag.touch) return;
      var tp = touchPoint(e);
      if (!tp) return;
      var piece = state.pieces.filter(function (p) { return p.id === drag.id; })[0];
      if (!piece) return;
      var dx = (tp.clientX - drag.x) * drag.scale;
      var dy = (tp.clientY - drag.y) * drag.scale;
      var b = drag.box;
      piece.box = drag.resize ?
        clampBox([b[0], b[1], b[2] + dx, b[3] + dy]) :
        clampBox([b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy]);
      renderBoxes();
      e.preventDefault();
    }, { passive: false });
    layer.addEventListener("touchend", end);
    layer.addEventListener("touchcancel", end);
  }

  // ---- list + fabrics -------------------------------------------------

  function renderList() {
    var list = $("dzList");
    if (!list) return;
    list.innerHTML = state.pieces.map(function (p) {
      var fab = p.meta ?
        '<button type="button" class="dz-fab" data-pick="' + p.id + '">' +
          '<img src="/' + esc((p.meta.image || "").replace(/^\/+/, "")) +
          '" alt=""><span dir="auto">' +
          esc(state.lang === "ar" ? p.meta.name_ar : p.meta.name_en) +
          "</span></button>" :
        '<button type="button" class="dz-fab empty" data-pick="' + p.id +
          '"><span>' + esc(t("chooseFabric")) + "</span></button>";
      return '<div class="dz-row' + (state.sel === p.id ? " sel" : "") +
        '" data-row="' + p.id + '"><span class="dz-n">' + num(p.id, 0) +
        '</span><div><div class="dz-name" dir="auto">' + esc(p.name) +
        '</div><div class="dz-type">' + esc(typeLabel(p.type)) + " · " +
        num(p.box[2] - p.box[0], 0) + "×" + num(p.box[3] - p.box[1], 0) +
        " px</div></div>" + fab +
        '<button type="button" class="dz-del" data-del="' + p.id +
        '" aria-label="' + esc(t("removed")) + '">×</button></div>';
    }).join("");
    updateRenderBtn();
  }

  function updateRenderBtn() {
    var btn = $("dzRender");
    if (!btn) return;
    var ready = !!state.plan && state.pieces.some(function (p) { return p.code; });
    btn.disabled = !ready || state.busy;
  }

  function openBrowse(id) {
    state.browseFor = id;
    state.sel = id;
    renderList();
    renderBoxes();
    var panel = $("dzBrowse");
    panel.hidden = false;
    var piece = state.pieces.filter(function (p) { return p.id === id; })[0];
    panel.innerHTML = '<div class="browse-head"><b>' + esc(t("browseTitle")) +
      " · " + num(id, 0) + " " + esc(piece ? piece.name : "") +
      '</b><button type="button" class="ghost-btn" id="dzBrowseClose">' +
      esc(t("closeBrowse")) + "</button></div>" +
      '<div class="browse-grid"><span class="typing"><span></span>' +
      "<span></span><span></span></span></div>";
    $("dzBrowseClose").addEventListener("click", function () {
      panel.hidden = true;
      state.browseFor = null;
    });
    // Same catalog and filter as the consult browse panel: every plan
    // piece is upholstery, so the sofa-suitable set applies.
    fetch("/api/fabrics?suitable_for=sofa&usage=upholstery&limit=24")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (state.browseFor !== id) return;
        state.browseList = (data && data.fabrics) || [];
        var grid = panel.querySelector(".browse-grid");
        grid.innerHTML = state.browseList.map(function (f) {
          var name = state.lang === "ar" ? f.name_ar : f.name_en;
          return '<div class="browse-card"><img src="/' +
            esc((f.image || "").replace(/^\/+/, "")) + '" alt="' +
            esc(name) + '" loading="lazy">' +
            '<div class="browse-n" dir="auto">' + esc(name) + "</div>" +
            '<div class="browse-m">' + esc(f.code) + " · " +
            esc(fmt("sarPerM", num(f.price_sar_per_m, 0))) + "</div>" +
            '<button type="button" class="seeit" data-apply="' +
            esc(f.code) + '"><span>' + esc(t("applyOne")) +
            "</span></button></div>";
        }).join("");
      })
      .catch(function () {
        panel.querySelector(".browse-grid").textContent = t("sendFail");
      });
  }

  function assign(code) {
    var id = state.browseFor;
    var piece = state.pieces.filter(function (p) { return p.id === id; })[0];
    var meta = state.browseList.filter(function (f) { return f.code === code; })[0];
    if (!piece || !meta) return;
    piece.code = code;
    piece.meta = meta;
    $("dzBrowse").hidden = true;
    state.browseFor = null;
    renderList();
    renderBoxes();
  }

  function removePiece(id) {
    state.pieces = state.pieces.filter(function (p) { return p.id !== id; });
    if (state.sel === id) state.sel = null;
    if (state.browseFor === id) { $("dzBrowse").hidden = true; state.browseFor = null; }
    renderList();
    renderBoxes();
  }

  // ---- render (SSE) ---------------------------------------------------

  function setStep(n, retry) {
    var items = document.querySelectorAll("#dzSteps li");
    for (var i = 0; i < 2 && i < items.length; i++) {
      items[i].className = i < n ? "done" : i === n ? "active" : "";
    }
    var row = $("dzRetryRow");
    row.hidden = !retry;
    row.className = retry ? "active" : "";
  }

  function startRender() {
    if (state.busy || !state.plan) return;
    var assigned = state.pieces.filter(function (p) { return p.code; });
    if (!assigned.length) return;
    state.busy = true;
    updateRenderBtn();
    $("dzModal").hidden = false;
    document.body.classList.add("modal-open");
    $("dzLoading").hidden = false;
    $("dzResult").hidden = true;
    $("dzError").hidden = true;
    $("dzErrClose").hidden = true;
    setStep(0, false);
    var body = { image_path: state.plan.image_path,
                 pieces: state.pieces.map(function (p) {
                   return { id: p.id, name: p.name, type: p.type,
                            box: p.box, code: p.code };
                 }) };
    fetch("/api/designer/render/stream", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok || !r.body) throw new Error("render");
      var reader = r.body.getReader();
      var dec = new TextDecoder();
      var buf = "";
      var settled = false;
      function pump() {
        return reader.read().then(function (step) {
          if (step.done) {
            if (!settled) fail(t("renderFail"));
            return;
          }
          buf += dec.decode(step.value, { stream: true });
          var parts = buf.split("\n\n");
          buf = parts.pop();
          parts.forEach(function (chunk) {
            chunk.split("\n").forEach(function (line) {
              if (line.indexOf("data:") !== 0) return;
              var evt;
              try { evt = JSON.parse(line.slice(5).trim()); } catch (e) { return; }
              if (evt.type === "step") {
                if (evt.label === "edit") setStep(0, false);
                else if (evt.label === "check") setStep(1, false);
                else if (evt.label === "retry") setStep(0, true);
              } else if (evt.type === "done") {
                settled = true;
                finish(evt.result || {});
              } else if (evt.type === "error") {
                settled = true;
                fail(evt.message || t("renderFail"));
              }
            });
          });
          if (!settled) return pump();
        });
      }
      return pump();
    }).catch(function () { fail(t("renderFail")); });
  }

  function fail(message) {
    state.busy = false;
    updateRenderBtn();
    $("dzError").textContent = message;
    $("dzError").hidden = false;
    $("dzErrClose").hidden = false;
  }

  function finish(res) {
    state.busy = false;
    state.render = res;
    updateRenderBtn();
    $("dzLoading").hidden = true;
    $("dzResult").hidden = false;
    renderResult(res);
  }

  function renderResult(res) {
    var plan = "/" + (res.plan_url || state.plan.image_path).replace(/^\/+/, "");
    var after = "/" + (res.render_url || "").replace(/^\/+/, "");
    $("dzBeforeImg").src = plan;
    $("dzAfterImg").src = after;
    $("dzDownload").href = after;
    setRange(50);
    var checks = {};
    (res.checks || []).forEach(function (c) { checks[c.id] = c; });
    $("dzLegend").innerHTML = (res.legend || []).map(function (it) {
      var name = state.lang === "ar" ? it.name_ar : it.name_en;
      var c = checks[it.id];
      var chk = !it.code ? "" : c && c.ok ?
        '<span class="ok">' + esc(t("checkOk")) + "</span>" :
        c ? '<span class="bad">' + esc(t("checkBad")) + "</span>" : "";
      return '<div class="dz-lg"><span class="dz-n">' + num(it.id, 0) +
        "</span>" + (it.image ? '<img src="/' + esc(it.image) + '" alt="">' :
        "<span></span>") + '<div dir="auto"><b>' + esc(it.name) + "</b>" +
        (name ? " → " + esc(name) : "") + ' <span class="dz-lg-code">' +
        esc(it.code || "") + (it.material ? " · " + esc(it.material) : "") +
        "</span></div>" + chk + "</div>";
    }).join("");
    var q = res.quote || {};
    var lines = (q.items || []).map(function (it) {
      return '<div class="sum-row"><div>' + num(it.id, 0) + " " + esc(it.name) +
        " · " + esc(it.code) + " · " + esc(fmt("meters", num(it.meters))) +
        " × " + esc(fmt("sarPerM", num(it.price_sar_per_m, 0))) + " = " +
        esc(fmt("sar", num(it.line_total, 2))) + "</div></div>";
    }).join("");
    var html = lines;
    if (q.items && q.items.length) {
      html += '<div class="sum-total"><b>' + esc(t("totalLabel")) + "</b> " +
        esc(fmt("sar", num(q.total, 2))) + "</div>" +
        '<p class="coming">' + esc(t("preliminaryNote")) + "</p>";
      if (q.co2 && q.co2.kg > 0) {
        html += '<div class="co2-line"><i data-lucide="leaf" aria-hidden="true"></i><div>' +
          esc(t("co2Line").replace("%d", num(q.co2.kg)).replace("%d", num(q.co2.waste_kg))) +
          ' <span class="co2-src">' + esc(t("co2Source")) + "</span></div></div>";
      }
    }
    $("dzQuote").innerHTML = html;
    icons();
  }

  function setRange(v) {
    $("dzRange").value = v;
    $("dzBefore").style.clipPath = "inset(0 " + (100 - v) + "% 0 0)";
    $("dzHandle").style.left = v + "%";
  }

  // ---- proposal PDF ---------------------------------------------------

  function downloadProposal() {
    var res = state.render;
    if (!res) return;
    var q = res.quote || {};
    var items = (q.items || []).map(function (it) {
      return { label: num(it.id, 0) + " · " + it.name, code: it.code,
               meters: it.meters, line_total: it.line_total };
    });
    var body = { lang: state.lang, mode: "plan",
                 prepared_by: $("dzPreparedBy").value || "",
                 before_url: res.plan_url || state.plan.image_path,
                 after_url: res.render_url, items: items,
                 total: q.total, co2: q.co2 || null };
    var st = $("dzPdfStatus");
    st.textContent = t("pdfBusy");
    st.hidden = false;
    fetch("/api/proposal/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok) throw new Error("pdf");
      return r.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "recover-proposal-" + state.lang + ".pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      st.textContent = t("pdfDone");
    }).catch(function () {
      st.textContent = t("pdfFail");
    });
  }

  function closeModal() {
    $("dzModal").hidden = true;
    document.body.classList.remove("modal-open");
  }

  // ---- boot -------------------------------------------------------------

  function boot() {
    state.lang = initialLang();
    applyI18n();
    icons();
    if (window.RCSwitcher && $("switcherMount")) {
      window.RCSwitcher.mount($("switcherMount"), {
        getLang: function () { return state.lang; },
        onPick: function (code) { setLang(code); }
      });
    }
    $("dzUploadBtn").addEventListener("click", function () { $("dzFile").click(); });
    $("dzDrop").addEventListener("click", function () { $("dzFile").click(); });
    $("dzDrop").addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("dzFile").click(); }
    });
    $("dzFile").addEventListener("change", function () {
      if (this.files && this.files[0]) uploadPlan(this.files[0]);
      this.value = "";
    });
    ["dragenter", "dragover"].forEach(function (ev) {
      $("dzDrop").addEventListener(ev, function (e) { e.preventDefault(); });
    });
    $("dzDrop").addEventListener("drop", function (e) {
      e.preventDefault();
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) uploadPlan(f);
    });
    $("dzRefind").addEventListener("click", function () {
      if (!state.busy) findPieces();
    });
    $("dzList").addEventListener("click", function (e) {
      var pick = e.target.closest("[data-pick]");
      if (pick) { openBrowse(+pick.dataset.pick); return; }
      var del = e.target.closest("[data-del]");
      if (del) { removePiece(+del.dataset.del); return; }
      var row = e.target.closest("[data-row]");
      if (row) { state.sel = +row.dataset.row; renderList(); renderBoxes(); }
    });
    $("dzBrowse").addEventListener("click", function (e) {
      var btn = e.target.closest("[data-apply]");
      if (btn) assign(btn.dataset.apply);
    });
    $("dzRender").addEventListener("click", startRender);
    $("dzRange").addEventListener("input", function () { setRange(+this.value); });
    $("dzClose").addEventListener("click", closeModal);
    $("dzErrClose").addEventListener("click", closeModal);
    $("dzProposal").addEventListener("click", downloadProposal);
    bindDrag();
    window.addEventListener("resize", renderBoxes);
  }

  // Exposed for the browser tests (box edits are state, not DOM).
  window.RCDesigner = {
    state: state,
    setPieces: function (list) {
      state.pieces = list.map(function (p) {
        return { id: p.id, name: p.name, type: p.type, box: p.box.slice(),
                 code: p.code || null, meta: p.meta || null };
      });
      renderList();
      renderBoxes();
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
