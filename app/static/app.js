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
      steps: { search: "Searching 80 fabrics…", claw: "Checking claw safety…", details: "Comparing details…", room: "Reading your room's colors…" },
      needPhoto: "Please upload a room photo first, then tap “See it in my space” again.",
      pieceYou: { sofa: "sofa", armchair: "armchair", curtains: "curtains", cushions: "cushions" },
      stepRetry: "Retrying with corrections",
      tryAgain: "Try again",
      followSwap: "Looks lovely in your space. Want to see the next fabric on it, or should I estimate the meters?",
      emptyLeadOptions: "Sure — which of these works for you?",
      emptyLeadRecs: "Here are my top picks for you:",
      emptyLeadGeneric: "Could you tell me a little more about what you need?",
      viewAgain: "View again",
      rephoto: "Try on another photo",
      previewsTitle: "Your previews",
      previewsHint: "Tap one to view, two to compare",
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
      seeIt: "شاهده في مساحتك",
      comingSoon: "قريباً",
      perMeter: "ر.س/م",
      matchSection: "لماذا هذا القماش",
      relaxSection: "عدّلنا لك",
      sendFail: "عذراً، حدث خطأ. حاول مرة أخرى.",
      thinkingNote: "لحظة، أفكر…",
      uploadFail: "فشل الرفع. جرب صورة JPG أو PNG.",
      voiceFail: "عذراً، ما سمعتك زين. حاول مرة ثانية.",
      micLabel: "إدخال صوتي",
      steps: { search: "أدوّر في ٨٠ قماش…", claw: "أتأكد إنها آمنة من الخدش…", details: "أقارن التفاصيل…", room: "أقرأ ألوان مساحتك…" },
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
      roomTitle: "مساحتك",
      roomType: "الغرفة",
      style: "الستايل",
      light: "الإضاءة",
      piece: "القطعة",
      palette: "ألوان الجدران",
      pieceYou: { sofa: "كنبتك", armchair: "كرسيك", curtains: "ستارتك", cushions: "وسايدك" },
      stepRetry: "أعيد المحاولة بتعديل",
      tryAgain: "حاول مرة ثانية",
      followSwap: "شكلها حلو في مجلسك. تبي أجرب القماش الثاني، ولا أحسب لك الأمتار؟",
      emptyLeadOptions: "تمام — أي واحد يناسبك؟",
      emptyLeadRecs: "هذه أفضل اختياراتي لك:",
      emptyLeadGeneric: "ممكن تقول لي أكثر عن اللي تحتاجه؟",
      viewAgain: "شاهدها مرة ثانية",
      rephoto: "جرّب على صورة ثانية",
      previewsTitle: "معايناتك",
      previewsHint: "اضغط على وحدة للعرض، وثنتين للمقارنة",
      chips: ["تنجيد", "ستائر", "وسائد", "تشكيلة"],
      snag: { low: "خطر خدش منخفض", medium: "خطر خدش متوسط", high: "خطر خدش مرتفع", unknown: "غير معروف" },
      features: {},
      matched: {},
      relaxed: {}
    },
    hi: {
      tagline: "लुक बदलें, फर्नीचर नहीं।",
      forYou: "आपके लिए",
      emptyRecs: "आपके सुझाए कपड़े यहाँ दिखेंगे।",
      dropHint: "कमरे की फोटो यहाँ डालें, या चुनने के लिए टैप करें",
      placeholder: "कपड़ों के बारे में पूछें…",
      analyzing: "आपका कमरा देख रहा हूँ…",
      seeIt: "इसे अपनी जगह पर देखें",
      comingSoon: "जल्द आ रहा है",
      perMeter: "SAR/मी",
      matchSection: "यह कपड़ा क्यों",
      relaxSection: "आपके लिए बदला",
      sendFail: "माफ़ करें, कुछ गड़बड़ हुई। फिर कोशिश करें।",
      uploadFail: "अपलोड विफल। JPG या PNG फोटो भेजें।",
      voiceFail: "माफ़ करें, सुन नहीं पाया। फिर कोशिश करें।",
      micLabel: "आवाज़ से पूछें",
      needPhoto: "पहले कमरे की फोटो भेजें, फिर “इसे अपनी जगह पर देखें” दबाएँ।",
      tailoring: "%s सजा रहा हूँ…",
      pieceWord: { sofa: "सोफ़ा", armchair: "कुर्सी", curtains: "पर्दे", cushions: "कुशन" },
      stepDetect: "टुकड़ा पहचान रहा हूँ",
      stepApply: "कपड़ा लगा रहा हूँ",
      stepCheck: "मिलान जाँच रहा हूँ",
      stillWorking: "अभी चल रहा है — मुश्किल कमरों में कुछ मिनट लगते हैं।",
      matchBadge: "कपड़ा मिलान %d/10",
      downloadLabel: "डाउनलोड",
      closeLabel: "बंद करें",
      swapFail: "झलक नहीं बनी। दूसरी फोटो से फिर कोशिश करें।",
      roomTitle: "आपका कमरा",
      roomType: "कमरा",
      style: "स्टाइल",
      light: "रोशनी",
      piece: "टुकड़ा",
      palette: "दीवार के रंग",
      chips: ["अपहोल्स्ट्री", "पर्दे", "कुशन", "मिक्स"],
      steps: { search: "80 कपड़े खोज रहा हूँ…", claw: "पंजों से सुरक्षा जाँच रहा हूँ…", details: "विवरण मिला रहा हूँ…", room: "आपके कमरे के रंग पढ़ रहा हूँ…" },
      thinkingNote: "सोच रहा हूँ…",
      snag: { low: "पंजा-सुरक्षित", medium: "मध्यम जोखिम", high: "ज्यादा जोखिम", unknown: "अज्ञात" },
      pieceYou: { sofa: "आपका सोफ़ा", armchair: "आपकी कुर्सी", curtains: "आपके पर्दे", cushions: "आपके कुशन" },
      stepRetry: "सुधार के साथ पुनः प्रयास",
      tryAgain: "फिर से कोशिश करें",
      followSwap: "आपके स्थान पर सुंदर लग रहा है। अगला कपड़ा देखना चाहेंगे, या मीटर का अनुमान लगाऊँ?",
      emptyLeadOptions: "बताइए — इनमें से कौन सा चलेगा?",
      emptyLeadRecs: "ये मेरे सबसे अच्छे सुझाव हैं:",
      emptyLeadGeneric: "अपनी ज़रूरत के बारे में थोड़ा और बताइए?",
      viewAgain: "फिर से देखें",
      rephoto: "दूसरी फोटो पर आज़माएँ",
      previewsTitle: "आपकी झलकियाँ",
      previewsHint: "देखने के लिए एक, तुलना के लिए दो दबाएँ",
      features: {},
      matched: {},
      relaxed: {}
    },
    fr: {
      tagline: "Changez le look, pas le mobilier.",
      forYou: "Pour vous",
      emptyRecs: "Vos tissus recommandés apparaîtront ici.",
      dropHint: "Déposez une photo de la pièce, ou touchez pour choisir",
      placeholder: "Posez vos questions tissus…",
      analyzing: "J'analyse votre pièce…",
      seeIt: "Voir chez moi",
      comingSoon: "Bientôt",
      perMeter: "SAR/m",
      matchSection: "Pourquoi ce tissu",
      relaxSection: "Ajusté pour vous",
      sendFail: "Désolé, une erreur est survenue. Réessayez.",
      uploadFail: "Échec de l'envoi. Envoyez une photo JPG ou PNG.",
      voiceFail: "Désolé, je n'ai pas entendu. Réessayez.",
      micLabel: "Entrée vocale",
      needPhoto: "Envoyez d'abord une photo, puis touchez « Voir chez moi ».",
      tailoring: "J'habille votre %s…",
      pieceWord: { sofa: "canapé", armchair: "fauteuil", curtains: "rideaux", cushions: "coussins" },
      stepDetect: "Je détecte la pièce",
      stepApply: "J'applique le tissu",
      stepCheck: "Je vérifie l'harmonie",
      stillWorking: "Je travaille encore — les pièces complexes prennent quelques minutes.",
      matchBadge: "Tissu assorti %d/10",
      downloadLabel: "Télécharger",
      closeLabel: "Fermer",
      swapFail: "Aperçu impossible. Réessayez avec une autre photo.",
      roomTitle: "Votre pièce",
      roomType: "Pièce",
      style: "Style",
      light: "Lumière",
      piece: "Pièce",
      palette: "Palette des murs",
      chips: ["Tapisserie", "Rideaux", "Coussins", "Mixte"],
      steps: { search: "Je parcours 80 tissus…", claw: "Je vérifie la résistance aux griffes…", details: "Je compare les détails…", room: "Je lis les couleurs de votre pièce…" },
      thinkingNote: "Je réfléchis…",
      snag: { low: "Résistant aux griffes", medium: "Risque moyen", high: "Risque élevé", unknown: "N/A" },
      pieceYou: { sofa: "canapé", armchair: "fauteuil", curtains: "rideaux", cushions: "coussins" },
      stepRetry: "Nouvel essai corrigé",
      tryAgain: "Réessayer",
      followSwap: "C'est ravissant chez vous. Voir le tissu suivant, ou estimer le métrage ?",
      emptyLeadOptions: "Dites-moi — lequel vous convient ?",
      emptyLeadRecs: "Voici mes meilleurs choix :",
      emptyLeadGeneric: "Pouvez-vous m'en dire un peu plus ?",
      viewAgain: "Revoir",
      rephoto: "Essayer sur une autre photo",
      previewsTitle: "Vos aperçus",
      previewsHint: "Touchez-en un pour voir, deux pour comparer",
      features: {},
      matched: {},
      relaxed: {}
    },
    es: {
      tagline: "Cambia el look, no el sofá.",
      forYou: "Para ti",
      emptyRecs: "Tus telas recomendadas aparecerán aquí.",
      dropHint: "Suelta una foto de la habitación, o toca para elegir",
      placeholder: "Pregunta por telas…",
      analyzing: "Estoy analizando tu espacio…",
      seeIt: "Verlo en mi espacio",
      comingSoon: "Pronto",
      perMeter: "SAR/m",
      matchSection: "Por qué esta tela",
      relaxSection: "Ajustado para ti",
      sendFail: "Perdón, algo falló. Inténtalo de nuevo.",
      uploadFail: "Subida fallida. Envía una foto JPG o PNG.",
      voiceFail: "Perdón, no te escuché. Inténtalo de nuevo.",
      micLabel: "Entrada de voz",
      needPhoto: "Sube primero una foto y luego toca «Verlo en mi espacio».",
      tailoring: "Vistiendo tu %s…",
      pieceWord: { sofa: "sofá", armchair: "sillón", curtains: "cortinas", cushions: "cojines" },
      stepDetect: "Detecto la pieza",
      stepApply: "Aplico la tela",
      stepCheck: "Compruebo la armonía",
      stillWorking: "Sigo trabajando — las habitaciones complejas tardan unos minutos.",
      matchBadge: "Tela compatible %d/10",
      downloadLabel: "Descargar",
      closeLabel: "Cerrar",
      swapFail: "No se pudo generar la vista. Prueba con otra foto.",
      roomTitle: "Tu espacio",
      roomType: "Habitación",
      style: "Estilo",
      light: "Luz",
      piece: "Pieza",
      palette: "Paleta de paredes",
      chips: ["Tapicería", "Cortinas", "Cojines", "Mixto"],
      steps: { search: "Busco entre 80 telas…", claw: "Compruebo la resistencia a las garras…", details: "Comparo los detalles…", room: "Leo los colores de tu espacio…" },
      thinkingNote: "Estoy pensando…",
      snag: { low: "Resistente a garras", medium: "Riesgo medio", high: "Riesgo alto", unknown: "N/D" },
      pieceYou: { sofa: "sofá", armchair: "sillón", curtains: "cortinas", cushions: "cojines" },
      stepRetry: "Reintento con correcciones",
      tryAgain: "Reintentar",
      followSwap: "Se ve precioso en tu espacio. ¿Vemos la siguiente tela o calculo los metros?",
      emptyLeadOptions: "Dime — ¿cuál te conviene?",
      emptyLeadRecs: "Estas son mis mejores opciones:",
      emptyLeadGeneric: "¿Me cuentas un poco más lo que necesitas?",
      viewAgain: "Ver de nuevo",
      rephoto: "Probar en otra foto",
      previewsTitle: "Tus vistas previas",
      previewsHint: "Toca una para ver, dos para comparar",
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

  var FEATURE_ICONS = {
    "pet-friendly": "paw-print",
    "scratch-resistant": "shield",
    "easy-clean": "sparkles",
    "stain-resistant": "droplet-off",
    "washable": "washing-machine",
    "antibacterial": "shield-plus",
    "fire-resistant": "flame",
    "blackout": "moon",
    "fade-resistant": "sun",
    "thermal-insulating": "thermometer",
    "sound-absorbing": "volume-x",
    "hypoallergenic": "flower-2",
    "eco-friendly": "recycle",
    "crease-resistant": "wind"
  };

  function icons() {
    if (window.lucide && lucide.createIcons) {
      lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
    }
  }

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

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && STRINGS[q]) return q;
    var nav = (navigator.language || "en").toLowerCase();
    if (nav.indexOf("ar") === 0) return "ar";
    if (nav.indexOf("hi") === 0) return "hi";
    if (nav.indexOf("fr") === 0) return "fr";
    if (nav.indexOf("es") === 0) return "es";
    return "en";
  }

  function newSessionId() {
    return "web-" + Math.random().toString(36).slice(2, 10);
  }

  function loadSessionId() {
    try {
      var saved = window.localStorage.getItem("recover_sid");
      if (saved) return saved;
      var fresh = newSessionId();
      window.localStorage.setItem("recover_sid", fresh);
      return fresh;
    } catch (e) {
      return newSessionId();
    }
  }

  function saveSessionId(sid) {
    try { window.localStorage.setItem("recover_sid", sid); } catch (e) {}
  }

  var state = {
    lang: initialLang(),
    pinned: false,
    sessionId: loadSessionId(),
    booted: false,
    roomPhoto: null,
    detectedPiece: null,
    lastRoom: null,
    lastDetected: null,
    lastRecs: [],
    lastOptions: [],
    swaps: {},
    prevList: [],
    compareSel: [],
    pendingSwapCode: null,
    lastSwap: null
  };

  var $ = function (id) { return document.getElementById(id); };
  var messagesEl, chipsEl, recsEl, roomCardEl, composerInput;

  var UI_LANGS = ["en", "ar", "hi", "fr", "es"];
  var RTL_LANGS = ["ar", "ur", "fa"];
  var GREET = { ar: "مرحبا", hi: "नमस्ते", fr: "Bonjour", es: "Hola",
                en: "Hello" };

  function t(key) {
    var pack = STRINGS[state.lang] || {};
    if (pack[key] !== undefined) return pack[key];
    return STRINGS.en[key];
  }

  function featLabel(key) {
    var k = String(key || "");
    if (k.indexOf("fitted-") === 0) k = k.slice("fitted-".length);
    if (k.indexOf("feat-") === 0) k = k.slice("feat-".length);
    var pair = FEATURE_LABELS[k] || [key, key];
    return state.lang === "ar" ? pair[1] : pair[0];
  }

  function toArabicDigits(value) {
    return String(value).replace(/\d/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[+d]; });
  }

  function formatPrice(sar) {
    if (state.lang === "ar") return toArabicDigits(sar) + " ر.س/م";
    return sar + " " + t("perMeter");
  }

  function notFeatureLabel(key) {
    var label = featLabel(key);
    if (state.lang === "ar") return "مو " + label;
    return "Not " + label.charAt(0).toLowerCase() + label.slice(1);
  }

  function budgetPill(rb) {
    var price = state.lang === "ar" ? toArabicDigits(rb.price) + " ر.س/م" : rb.price + " SAR/m";
    var over = state.lang === "ar" ? toArabicDigits(rb.over) : rb.over;
    if (state.lang === "ar") return price + " — أعلى من ميزانيتك بـ " + over;
    return price + " — " + over + " over budget";
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

  function isRTL() { return RTL_LANGS.indexOf(state.lang) >= 0; }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.documentElement.dir = isRTL() ? "rtl" : "ltr";
    document.body.classList.toggle("ar", isRTL());
    if (state.lastRoom) renderRoomCard(state.lastRoom, state.lastDetected);
    if (state.lastRecs && state.lastRecs.length) renderRecs(state.lastRecs);
    renderStrip();
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
    });
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
        state.booted = true;
        send(label);
      });
      chipsEl.appendChild(b);
    });
    if (!state.booted) chipsEl.hidden = false;
  }

  function renderOptions(list) {
    chipsEl.innerHTML = "";
    (list || []).forEach(function (label) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.addEventListener("click", function () {
        chipsEl.hidden = true;
        state.booted = true;
        send(label);
      });
      chipsEl.appendChild(b);
    });
    if ((list || []).length) chipsEl.hidden = false;
  }

  function setLang(code, greet) {
    state.lang = STRINGS[code] ? code : "en";
    state.pinned = true;
    applyI18n();
    renderChips();
    if (window.RCSwitcher) window.RCSwitcher.refresh();
    if (!greet) return;
    state.sessionId = newSessionId();
    saveSessionId(state.sessionId);
    state.booted = false;
    state.roomPhoto = null;
    state.detectedPiece = null;
    state.lastRoom = null;
    state.lastDetected = null;
    state.lastRecs = [];
    state.lastOptions = [];
    state.swaps = {};
    state.prevList = [];
    state.compareSel = [];
    state.pendingSwapCode = null;
    state.lastSwap = null;
    messagesEl.innerHTML = "";
    recsEl.innerHTML = "";
    roomCardEl.hidden = true;
    $("roomDiv").hidden = true;
    renderStrip();
    bootGreeting();
  }

  function autoLang(res) {
    if (state.pinned || !res) return;
    var d = res.detected_lang;
    if (d && UI_LANGS.indexOf(d) >= 0 && d !== state.lang) {
      state.lang = d;
      applyI18n();
    }
  }

  var MIC_BADGE = '<span class="voice-badge" aria-hidden="true"><i data-lucide="mic"></i></span>';

  var AVATAR = '<img class="avatar" src="/brand/mark-plain.svg" alt="ReCover">';

  function formatReply(text) {
    return esc(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function addMsg(text, who, photo, voice) {
    var div = document.createElement("div");
    div.className = "msg " + who;
    if (who === "them") {
      var avWrap = document.createElement("span");
      avWrap.innerHTML = AVATAR;
      div.appendChild(avWrap.firstChild);
    }
    var body = document.createElement("div");
    body.setAttribute("dir", "auto");
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
    if (voice) icons();
    return div;
  }

  function stepLabel(key) {
    var map = t("steps") || {};
    if (map[key] !== undefined) return map[key];
    if (key === "thinking") return t("thinkingNote");
    return key;
  }

  function showStep(key) {
    var el = document.getElementById("agentStep");
    if (!el) return;
    el.textContent = stepLabel(key);
    el.classList.remove("swap");
    void el.offsetWidth;
    el.classList.add("swap");
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function pendingBubble() {
    var div = document.createElement("div");
    div.className = "msg them";
    div.id = "pending";
    div.innerHTML = AVATAR +
      '<div dir="auto"><div class="agent-step" id="agentStep"></div>' +
      '<span class="typing" id="pDots"><span></span><span></span><span></span></span>' +
      '<span class="ptext" id="pText"></span></div>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function leadIn(res) {
    if (res && res.reply && res.reply.trim()) return res.reply;
    var hasOpts = res && res.options && res.options.length;
    var hasRecs = res && res.recommendations && res.recommendations.length;
    if (hasOpts) return t("emptyLeadOptions");
    if (hasRecs) return t("emptyLeadRecs");
    return t("emptyLeadGeneric");
  }

  function finalizePending(reply) {
    var pending = document.getElementById("pending");
    if (!pending) return null;
    var step = document.getElementById("agentStep");
    if (step) step.remove();
    var dots = document.getElementById("pDots");
    if (dots) dots.remove();
    var body = document.getElementById("pText");
    var text = (reply && reply.trim()) ? reply :
      (body && body.textContent && body.textContent.trim() ?
        body.textContent : t("emptyLeadGeneric"));
    if (body) body.innerHTML = formatReply(text);
    pending.removeAttribute("id");
    return pending;
  }

  function dropPending() {
    var pending = document.getElementById("pending");
    if (pending) pending.remove();
  }

  function typingOn() {
    var div = document.createElement("div");
    div.className = "msg them";
    div.id = "typing";
    div.innerHTML = '<img class="avatar" src="/brand/mark-plain.svg" alt="ReCover"><span class="typing"><span></span><span></span><span></span></span>';
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
      var init = { method: (opts && opts.method) || "POST" };
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
    return "snag " + (level === "low" ? "snag-low" : level === "medium" ? "snag-medium" : level === "high" ? "snag-high" : "snag-unknown");
  }

  function renderRoomCard(room, detectedPiece) {
    if (!room) { roomCardEl.hidden = true; $("roomDiv").hidden = true; return; }
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
    roomCardEl.setAttribute("dir", "auto");
    roomCardEl.hidden = false;
    $("roomDiv").hidden = false;
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
      var desc = state.lang === "ar" ? (r.description_ar || "") : (r.description_en || "");
      var feats = (r.features || []).map(function (f) {
        var icon = FEATURE_ICONS[f] || "sparkles";
        var label = featLabel(f);
        return '<span class="feat" title="' + esc(label) + '" aria-label="' + esc(label) +
          '"><i data-lucide="' + icon + '" aria-hidden="true"></i></span>';
      }).join("");
      var matched = (r.matched || []).map(function (m) {
        return '<li class="yes"><span>✓</span> ' + esc(featLabel(m)) + "</li>";
      }).join("");
      var relaxed = (r.relaxed || []).map(function (m) {
        return '<li class="warn"><span>⚠</span> ' + esc(relaxLabel(m)) + "</li>";
      }).join("");
      var relaxedFeats = (r.relaxed_features || []).map(function (f) {
        return '<li class="warn"><span>⚠</span> ' + esc(notFeatureLabel(f)) + "</li>";
      }).join("");
      if (r.relaxed_budget) {
        relaxed += '<li class="warn"><span>⚠</span> ' + esc(budgetPill(r.relaxed_budget)) + "</li>";
      }
      var receipts = "";
      if (matched || relaxed || relaxedFeats) {
        receipts = '<ul class="receipts">' + matched + relaxed + relaxedFeats + "</ul>";
      }
      var done = state.swaps[r.code];
      var action;
      if (done && done.result_url) {
        action = '<div class="swap-done">' +
          '<img class="swap-thumb" src="/' + esc(done.result_url) + '" alt="' + esc(name) + '" data-code="' + esc(r.code) + '">' +
          '<div class="swap-done-btns">' +
          '<button class="seeit review" type="button" data-code="' + esc(r.code) + '"><span>' + esc(t("viewAgain")) + "</span></button>" +
          '<button class="ghost rephoto" type="button" data-code="' + esc(r.code) + '"><span>' + esc(t("rephoto")) + "</span></button>" +
          "</div></div>";
      } else {
        action = '<button class="seeit" type="button" data-code="' + esc(r.code) + '">' +
          '<i data-lucide="wand-sparkles" aria-hidden="true"></i><span>' + esc(t("seeIt")) + "</span></button>";
      }
      card.innerHTML =
        '<div class="swatch"><img src="/' + esc(r.image) + '" alt="' + esc(name) + '" loading="lazy">' +
        '<span class="code-pill">' + esc(r.code) + "</span></div>" +
        '<div class="body" dir="auto">' +
        '<div class="name">' + esc(name) + "</div>" +
        '<div class="meta"><i data-lucide="ruler" aria-hidden="true"></i><span>' +
        esc(formatPrice(r.price_sar_per_m)) + "</span></div>" +
        (desc ? '<p class="desc">' + esc(desc) + "</p>" : "") +
        '<div class="featrow">' + feats +
        '<span class="' + snagClass(r.snag_risk) + '">' + esc(t("snag")[r.snag_risk] || r.snag_risk) + "</span></div>" +
        (r.reason ? '<p class="why">' + esc(r.reason) + "</p>" : "") +
        receipts + action + "</div>";
      recsEl.appendChild(card);
    });
    icons();
  }

  function handleResult(res) {
    autoLang(res);
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    state.lastRoom = res.room_analysis || null;
    state.lastDetected = res.detected_piece || null;
    if (res.recommendations && res.recommendations.length) {
      state.lastRecs = res.recommendations;
    }
    state.lastOptions = res.options || [];
    renderRoomCard(state.lastRoom, state.lastDetected);
    addMsg(leadIn(res), "them");
    if (state.lastRecs && state.lastRecs.length) renderRecs(state.lastRecs);
    if (state.lastOptions && state.lastOptions.length) renderOptions(state.lastOptions);
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
      if (items[i].hidden) continue;
      items[i].className = i < n ? "done" : i === n ? "active" : "";
    }
  }

  var SWAP_STEP = { segment: 0, edit: 1, composite: 1, verify: 2 };

  function swapFabricMeta(code) {
    var list = state.lastRecs || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].code === code) {
        return { code: list[i].code,
                 name_en: list[i].name_en, name_ar: list[i].name_ar,
                 price: list[i].price_sar_per_m,
                 image: list[i].image };
      }
    }
    return { code: code };
  }

  function openSwap(code, opts) {
    opts = opts || {};
    if (!state.roomPhoto && !opts.review) {
      addMsg(t("needPhoto"), "them");
      var dz = $("dropzone");
      dz.scrollIntoView({ behavior: "smooth", block: "center" });
      dz.classList.add("flash");
      setTimeout(function () { dz.classList.remove("flash"); }, 1600);
      return;
    }
    state.swapCode = code;
    state.swapRetried = !!opts.noRetry;
    var target = swapTarget();
    var words = t("pieceYou") || {};
    $("swapTitle").textContent =
      t("tailoring").replace("%s", words[target] || target);
    $("swapLoading").hidden = false;
    $("swapResult").hidden = true;
    $("swapCompare").hidden = true;
    $("swapStill").hidden = true;
    $("swapRetryRow").hidden = true;
    $("swapRetryRow").className = "";
    $("swapTryAgain").hidden = true;
    $("swapTryAgain").textContent = t("tryAgain");
    $("swapModal").hidden = false;
    document.body.classList.add("modal-open");
    setStep(0);
    clearSwapTimers();
    swapTimers.push(setTimeout(function () {
      if (!$("swapModal").hidden) $("swapStill").hidden = false;
    }, 180000));
    var meta = swapFabricMeta(code);
    var reader = null;
    try {
      fetch("/api/swap/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId,
                               image_path: state.roomPhoto,
                               fabric_code: code, target: target })
      }).then(function (r) {
        if (!r.ok || !r.body) throw new Error("HTTP " + r.status);
        reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function onEvt(evt) {
          if (evt.type === "step") {
            if (evt.label === "retry") {
              var row = $("swapRetryRow");
              row.hidden = false;
              row.className = "active";
            } else if (SWAP_STEP[evt.label] !== undefined) {
              var n = SWAP_STEP[evt.label];
              var items = document.querySelectorAll("#swapSteps li");
              for (var i = 0; i < 3 && i < items.length; i++) {
                items[i].className = i < n ? "done" : i === n ? "active" : "";
              }
            }
          } else if (evt.type === "done") {
            try { reader.cancel(); } catch (e) {}
            finalizeSwap(code, meta, evt.result || {});
          } else if (evt.type === "error") {
            try { reader.cancel(); } catch (e) {}
            hideSwapModal();
            addMsg(t("swapFail"), "them");
          }
        }
        function pump() {
          return reader.read().then(function (step) {
            if (step.done) return;
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
            return pump();
          });
        }
        return pump();
      }).catch(function () {
        if (!$("swapResult") || $("swapResult").hidden) {
          hideSwapModal();
          addMsg(t("swapFail"), "them");
        }
      });
    } catch (e) {
      hideSwapModal();
      addMsg(t("swapFail"), "them");
    }
  }

  function finalizeSwap(code, meta, res) {
    clearSwapTimers();
    var scores = res.scores || {};
    var vals = [scores.color, scores.pattern, scores.scale,
                scores.isolation].map(function (v) { return v || 0; });
    var match = Math.min.apply(null, vals);
    var before = state.roomPhoto ?
      "/" + state.roomPhoto.replace(/^\/+/, "") : "";
    var after = "/" + (res.result_url || "").replace(/^\/+/, "");
    renderSwapResult(before, after, res, match, vals, meta);
    var entry = { fabric_code: code,
                  result_url: res.result_url || "",
                  mask_url: res.mask_url || "",
                  before_url: state.roomPhoto || "",
                  scores: scores, attempts: res.attempts || 1,
                  created_at: Date.now() / 1000, meta: meta };
    state.prevList.push(entry);
    state.swaps[code] = entry;
    state.lastSwap = entry;
    renderStrip();
    if (state.lastRecs && state.lastRecs.length) renderRecs(state.lastRecs);
    var showTry = match < 8 && (res.attempts || 1) < 2 && !state.swapRetried;
    $("swapTryAgain").hidden = !showTry;
  }

  function renderSwapResult(before, after, res, match, vals, meta) {
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
    var name = meta ? (state.lang === "ar" ? meta.name_ar || meta.code
                                           : meta.name_en || meta.code)
                    : "";
    var fabric = $("baFabric");
    if (meta && (meta.image || name)) {
      $("baFabricImg").src = meta.image ? "/" + meta.image : "";
      $("baFabricName").textContent = name || meta.code || "";
      $("baFabricCode").textContent = meta.code || "";
      $("baFabricPrice").textContent =
        meta.price !== undefined ? formatPrice(meta.price) : "";
      fabric.hidden = false;
    } else {
      fabric.hidden = true;
    }
    var items = document.querySelectorAll("#swapSteps li");
    for (var i = 0; i < items.length; i++) items[i].className = "done";
    $("swapLoading").hidden = true;
    $("swapCompare").hidden = true;
    $("swapResult").hidden = false;
    icons();
  }

  function openSwapReview(entry) {
    var meta = entry.meta || { code: entry.fabric_code };
    var scores = entry.scores || {};
    var vals = [scores.color, scores.pattern, scores.scale,
                scores.isolation].map(function (v) { return v || 0; });
    var match = Math.min.apply(null, vals);
    $("swapTitle").textContent = t("tailoring")
      .replace("%s", (t("pieceYou") || {})[swapTarget()] || "");
    renderSwapResult("/" + (entry.before_url || "").replace(/^\/+/, ""),
                     "/" + (entry.result_url || "").replace(/^\/+/, ""),
                     { scores: scores }, match, vals, meta);
    var attempts = entry.attempts || 1;
    $("swapTryAgain").hidden = !(match < 8 && attempts < 2);
    $("swapTryAgain").textContent = t("tryAgain");
    state.swapCode = entry.fabric_code;
    state.swapRetried = true;
    state.lastSwap = null;
    $("swapLoading").hidden = true;
    $("swapModal").hidden = false;
    document.body.classList.add("modal-open");
  }

  function openSwapCompare(a, b) {
    function fig(entry) {
      var meta = entry.meta || {};
      var name = state.lang === "ar" ? (meta.name_ar || entry.fabric_code)
                                     : (meta.name_en || entry.fabric_code);
      return '<figure><img src="/' +
        esc((entry.result_url || "").replace(/^\/+/, "")) + '" alt="' +
        esc(name) + '"><figcaption>' + esc(name) + "</figcaption></figure>";
    }
    $("swapCompare").innerHTML = '<div class="compare-grid">' +
      fig(a) + fig(b) + "</div>";
    $("swapLoading").hidden = true;
    $("swapResult").hidden = true;
    $("swapCompare").hidden = false;
    $("swapTitle").textContent = "";
    $("swapModal").hidden = false;
    document.body.classList.add("modal-open");
  }

  function postSwapMessage(entry) {
    var meta = entry.meta || { code: entry.fabric_code };
    var name = state.lang === "ar" ? (meta.name_ar || meta.code || "")
                                   : (meta.name_en || meta.code || "");
    var scores = entry.scores || {};
    var vals = [scores.color, scores.pattern, scores.scale,
                scores.isolation].map(function (v) { return v || 0; });
    var match = Math.min.apply(null, vals);
    var div = document.createElement("div");
    div.className = "msg them";
    var fabricImg = meta.image ?
      '<img class="chat-swap-fabric" src="/' + esc(meta.image) + '" alt="">' : "";
    div.innerHTML = AVATAR + '<div dir="auto"><div class="chat-swap">' +
      '<img class="swap-thumb" src="/' +
      esc((entry.result_url || "").replace(/^\/+/, "")) + '" alt="' +
      esc(name) + '" data-code="' + esc(entry.fabric_code) + '">' +
      '<div class="chat-swap-row">' + fabricImg +
      "<div><div><b>" + esc(name) + "</b></div><div>" +
      esc(entry.fabric_code) +
      (meta.price !== undefined ? " · " + esc(formatPrice(meta.price)) : "") +
      "</div></div>" +
      '<span class="match-badge small">' +
      esc(t("matchBadge").replace("%d", match)) + "</span></div>" +
      '<p class="chat-follow">' + esc(t("followSwap")) + "</p>" +
      "</div></div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    icons();
  }

  function renderStrip() {
    var wrap = $("prevWrap");
    var strip = $("prevStrip");
    if (!wrap || !strip) return;
    strip.innerHTML = "";
    if (!state.prevList.length) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    state.prevList.forEach(function (p, idx) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "prev-thumb" +
        (state.compareSel.indexOf(idx) >= 0 ? " sel" : "");
      var meta = p.meta || {};
      var label = state.lang === "ar" ? (meta.name_ar || p.fabric_code)
                                      : (meta.name_en || p.fabric_code);
      b.title = label;
      b.setAttribute("aria-label", label);
      b.innerHTML = '<img src="/' +
        esc((p.result_url || "").replace(/^\/+/, "")) + '" alt="' +
        esc(label) + '"><span>' + esc(p.fabric_code) + "</span>";
      (function (i) {
        b.addEventListener("click", function () { onPrevTap(i); });
      })(idx);
      strip.appendChild(b);
    });
  }

  function onPrevTap(idx) {
    var sel = state.compareSel;
    if (sel.indexOf(idx) >= 0) {
      state.compareSel = [];
      openSwapReview(state.prevList[idx]);
      renderStrip();
      return;
    }
    if (sel.length === 1) {
      var a = state.prevList[sel[0]];
      var b = state.prevList[idx];
      state.compareSel = [];
      renderStrip();
      openSwapCompare(a, b);
      return;
    }
    state.compareSel = [idx];
    renderStrip();
  }

  function baUpdate(pct) {
    $("baBefore").style.clipPath =
      "inset(0 " + (100 - pct) + "% 0 0)";
    $("baHandle").style.left = pct + "%";
  }

  function hideSwapModal() {
    clearSwapTimers();
    $("swapModal").hidden = true;
    document.body.classList.remove("modal-open");
  }

  function closeSwap() {
    if (state.lastSwap) {
      postSwapMessage(state.lastSwap);
      state.lastSwap = null;
    }
    hideSwapModal();
  }

  function streamChat(text, imagePath) {
    return new Promise(function (resolve, reject) {
      var ctrl = new AbortController();
      var settled = false, stall = null;
      var gotToken = false;
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
      fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: text || "",
          image_path: imagePath || null,
          lang: state.pinned ? state.lang : null
        }),
        signal: ctrl.signal
      }).then(function (r) {
        if (!r.ok || !r.body) throw new Error("HTTP " + r.status);
        armStall();
        var reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function onEvt(evt) {
          if (evt.type === "step") {
            showStep(evt.label);
          } else if (evt.type === "token") {
            gotToken = true;
            var pText = document.getElementById("pText");
            var pDots = document.getElementById("pDots");
            if (pDots) pDots.remove();
            if (pText) {
              pText.textContent += evt.text;
              messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          } else if (evt.type === "done") {
            var clean = evt.result && evt.result.reply;
            finalizePending(clean !== undefined ? clean : null);
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
        if (gotToken) { finish(e); return; }
        postJSON("/api/chat", {
          session_id: state.sessionId,
          message: text || "",
          image_path: imagePath || null,
          lang: state.pinned ? state.lang : null
        }, 120000, 1).then(function (res) {
          res.fallback = true;
          finish(null, res);
        }).catch(finish);
      });
    });
  }

  function send(text, imagePath, photoPreview, silent) {
    if (!text && !imagePath) return;
    if (!silent) addMsg(text || "", "me", photoPreview);
    pendingBubble();
    var thinkingTimer = setTimeout(function () {
      var body = document.getElementById("pText");
      if (body && !body.textContent) showStep("thinking");
    }, 8000);
    function finish() {
      clearTimeout(thinkingTimer);
    }
    streamChat(text, imagePath).then(function (res) {
      finish();
      if (!res) { dropPending(); return; }
      if (res.fallback && res.reply) finalizePending(res.reply);
      handleStreamResult(res);
    }).catch(function () {
      finish();
      dropPending();
      addMsg(t("sendFail"), "them");
    });
  }

  function handleStreamResult(res) {
    autoLang(res);
    if (!res) return;
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    state.lastRoom = res.room_analysis || null;
    state.lastDetected = res.detected_piece || null;
    if (res.recommendations && res.recommendations.length) {
      state.lastRecs = res.recommendations;
    }
    state.lastOptions = res.options || [];
    renderRoomCard(state.lastRoom, state.lastDetected);
    if (state.lastRecs && state.lastRecs.length) {
      renderRecs(state.lastRecs);
    }
    if (state.lastOptions && state.lastOptions.length) {
      renderOptions(state.lastOptions);
    }
  }

  function upload(file) {
    var fd = new FormData();
    fd.append("file", file);
    var preview = URL.createObjectURL(file);
    addMsg("", "me", preview);
    chipsEl.hidden = true;
    state.booted = true;
    var note = addMsg(t("analyzing"), "them");
    fetchReq("/api/upload", { form: fd, timeoutMs: 60000, retries: 1 })
      .then(function (data) {
        note.remove();
        state.roomPhoto = data.image_path;
        typingOn();
        return postJSON("/api/chat", {
          session_id: state.sessionId,
          message: "",
          image_path: data.image_path,
          lang: state.pinned ? state.lang : null
        }, 120000, 1);
      })
      .then(function (res) {
        typingOff();
        handleResult(res);
        if (state.pendingSwapCode) {
          var code = state.pendingSwapCode;
          state.pendingSwapCode = null;
          openSwap(code);
        }
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
        send(data.text, null, null, true);
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
    icons();

    if (window.RCSwitcher && $("switcherMount")) {
      window.RCSwitcher.mount($("switcherMount"), {
        getLang: function () { return state.lang; },
        onPick: function (code) { setLang(code, true); }
      });
    }

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
      if (!e.target.closest) return;
      var review = e.target.closest(".review");
      if (review && review.dataset.code && state.swaps[review.dataset.code]) {
        openSwapReview(state.swaps[review.dataset.code]);
        return;
      }
      var rephoto = e.target.closest(".rephoto");
      if (rephoto && rephoto.dataset.code) {
        state.pendingSwapCode = rephoto.dataset.code;
        var dz = $("dropzone");
        dz.scrollIntoView({ behavior: "smooth", block: "center" });
        dz.classList.add("flash");
        setTimeout(function () { dz.classList.remove("flash"); }, 1600);
        return;
      }
      var thumb = e.target.closest(".swap-thumb");
      if (thumb && thumb.dataset.code && state.swaps[thumb.dataset.code]) {
        openSwapReview(state.swaps[thumb.dataset.code]);
        return;
      }
      var btn = e.target.closest(".seeit");
      if (btn && btn.dataset.code) openSwap(btn.dataset.code);
    });
    messagesEl.addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var thumb = e.target.closest(".swap-thumb");
      if (thumb && thumb.dataset.code && state.swaps[thumb.dataset.code]) {
        openSwapReview(state.swaps[thumb.dataset.code]);
      }
    });
    $("swapTryAgain").addEventListener("click", function () {
      if (state.swapCode) openSwap(state.swapCode, { noRetry: true });
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

    bootGreeting();
  }

  function bootGreeting() {
    typingOn();
    var sid = state.sessionId;
    postJSON("/api/chat", {
      session_id: sid,
      message: GREET[state.lang] || "Hello",
      lang: state.lang
    }, 60000, 1)
      .then(function (res) {
        if (sid !== state.sessionId) return;
        typingOff();
        handleResult(res);
        chipsEl.hidden = false;
        fetchPreviews();
      })
      .catch(function () {
        if (sid !== state.sessionId) return;
        typingOff();
        addMsg(t("sendFail"), "them");
      });
  }

  function fetchPreviews() {
    fetchReq("/api/session/" + encodeURIComponent(state.sessionId) +
             "/previews",
             { method: "GET", timeoutMs: 15000, retries: 1 })
      .then(function (data) {
        state.prevList = (data && data.previews) || [];
        state.swaps = {};
        state.prevList.forEach(function (p) {
          if (p && p.fabric_code) state.swaps[p.fabric_code] = p;
        });
        state.compareSel = [];
        renderStrip();
        if (state.lastRecs && state.lastRecs.length) renderRecs(state.lastRecs);
      })
      .catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
