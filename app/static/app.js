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
      steps: { photo: "Preparing your photo…", search: "Checking 80 fabrics…", claw: "Checking pet and kid safety…", details: "Picking the best 3…", room: "Looking at your room…" },
      needPhoto: "Please upload a room photo first, then tap “See it in my space” again.",
      uploadRetry: "Upload didn't go through — check your connection and try again.",
      roomView: "View",
      roomSub: "Your room",
      takePhoto: "Take or upload a photo",
      tryOn: "Try on my photo",
      thinking: "Thinking…",
      pieceYou: { sofa: "sofa", armchair: "armchair", curtains: "curtains", cushions: "cushions" },
      stepRetry: "Refining the fit",
      tryAgain: "Try again",
      followSwap: "Looks lovely in your space. Want to see the next fabric on it, or should I estimate the meters?",
      emptyLeadOptions: "Sure — which of these works for you?",
      emptyLeadRecs: "Here are my top picks for you:",
      emptyLeadGeneric: "Could you tell me a little more about what you need?",
      viewAgain: "View again",
      rephoto: "Try on another photo",
      previewsTitle: "Your previews",
      crumbHome: "Home",
      crumbConsult: "Consultation",
      newConsult: "New consultation",
      onlineNow: "Online · replies in your language",
      canvasEmpty: "Drop a photo of your sofa or chair",
      uploadPhoto: "Upload",
      trySample: "Or try a sample room:",
      sampleLiving: "Living room",
      sampleMajlis: "Majlis",
      sampleArmchair: "Armchair",
      holdBefore: "Hold for before",
      previewing: "Previewing",
      compareSide: "Compare side by side",
      previewsHint: "Tap one to view, two to compare",
      tailoring: "Tailoring your %s…",
      pieceWord: { sofa: "sofa", armchair: "armchair", curtains: "curtains", cushions: "cushions" },
      stepDetect: "Mapping the fabric area",
      stepApply: "Tailoring the fabric",
      stepCheck: "Checking the result",
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
      steps: { photo: "أجهز صورتك…", search: "أدوّر بين الثمانين قماش…", claw: "أتأكد من الأمان للحيوانات والأطفال…", details: "أختار لك أفضل 3…", room: "أطالع غرفتك…" },
      needPhoto: "ارفع صورة غرفتك أول، بعدين اضغط “شاهدها في مساحتك”.",
      uploadRetry: "ما تم الرفع — تأكد من الاتصال وحاول مرة ثانية.",
      roomView: "عرض",
      roomSub: "غرفتك",
      takePhoto: "صوّر أو ارفع صورة",
      tryOn: "جرّبه على صورتي",
      thinking: "لحظة…",
      tailoring: "نفصّل %s بقماشك…",
      pieceWord: { sofa: "الكنبة", armchair: "الكرسي", curtains: "الستائر", cushions: "الوسائد" },
      stepDetect: "أحدد مكان القماش",
      stepApply: "ألبّس قطعتك القماش",
      stepCheck: "أشيّك على النتيجة",
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
      stepRetry: "أضبط المقاس",
      tryAgain: "حاول مرة ثانية",
      followSwap: "شكلها حلو في مجلسك. تبي أجرب القماش الثاني، ولا أحسب لك الأمتار؟",
      emptyLeadOptions: "تمام — أي واحد يناسبك؟",
      emptyLeadRecs: "هذه أفضل اختياراتي لك:",
      emptyLeadGeneric: "ممكن تقول لي أكثر عن اللي تحتاجه؟",
      viewAgain: "شاهدها مرة ثانية",
      rephoto: "جرّب على صورة ثانية",
      previewsTitle: "معايناتك",
      crumbHome: "الرئيسية",
      crumbConsult: "استشارة",
      newConsult: "استشارة جديدة",
      onlineNow: "متصل · أرد عليك بلغتك",
      canvasEmpty: "أسقط صورة كنبتك أو كرسيك",
      uploadPhoto: "ارفع",
      trySample: "أو جرّب غرفة جاهزة:",
      sampleLiving: "غرفة معيشة",
      sampleMajlis: "مجلس",
      sampleArmchair: "كرسي",
      holdBefore: "اضغط لرؤية قبل",
      previewing: "تُعرض الآن",
      compareSide: "قارن جنباً إلى جنب",
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
      uploadRetry: "अपलोड नहीं हुआ — कनेक्शन देखकर फिर कोशिश करें।",
      roomView: "देखें",
      roomSub: "आपका कमरा",
      takePhoto: "फोटो लें या अपलोड करें",
      tryOn: "मेरी फोटो पर देखें",
      thinking: "सोच रहा हूँ…",
      tailoring: "%s सजा रहा हूँ…",
      pieceWord: { sofa: "सोफ़ा", armchair: "कुर्सी", curtains: "पर्दे", cushions: "कुशन" },
      stepDetect: "कपड़े की जगह तय कर रहा हूँ",
      stepApply: "कपड़ा चढ़ा रहा हूँ",
      stepCheck: "नतीजा जाँच रहा हूँ",
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
      steps: { photo: "आपकी फोटो तैयार कर रहा हूँ…", search: "80 कपड़े देख रहा हूँ…", claw: "पेट और बच्चों की सुरक्षा जाँच रहा हूँ…", details: "सबसे अच्छे 3 चुन रहा हूँ…", room: "आपका कमरा देख रहा हूँ…" },
      thinkingNote: "सोच रहा हूँ…",
      snag: { low: "पंजा-सुरक्षित", medium: "मध्यम जोखिम", high: "ज्यादा जोखिम", unknown: "अज्ञात" },
      pieceYou: { sofa: "आपका सोफ़ा", armchair: "आपकी कुर्सी", curtains: "आपके पर्दे", cushions: "आपके कुशन" },
      stepRetry: "फिट ठीक कर रहा हूँ",
      tryAgain: "फिर से कोशिश करें",
      followSwap: "आपके स्थान पर सुंदर लग रहा है। अगला कपड़ा देखना चाहेंगे, या मीटर का अनुमान लगाऊँ?",
      emptyLeadOptions: "बताइए — इनमें से कौन सा चलेगा?",
      emptyLeadRecs: "ये मेरे सबसे अच्छे सुझाव हैं:",
      emptyLeadGeneric: "अपनी ज़रूरत के बारे में थोड़ा और बताइए?",
      viewAgain: "फिर से देखें",
      rephoto: "दूसरी फोटो पर आज़माएँ",
      previewsTitle: "आपकी झलकियाँ",
      crumbHome: "होम",
      crumbConsult: "परामर्श",
      newConsult: "नया परामर्श",
      onlineNow: "ऑनलाइन · आपकी भाषा में जवाब",
      canvasEmpty: "अपने सोफ़े या कुर्सी की फ़ोटो डालें",
      uploadPhoto: "अपलोड",
      trySample: "या नमूना कमरा आज़माएँ:",
      sampleLiving: "लिविंग रूम",
      sampleMajlis: "मजलिस",
      sampleArmchair: "कुर्सी",
      holdBefore: "पहले देखने के लिए दबाएँ",
      previewing: "दिखाया जा रहा है",
      compareSide: "साथ-साथ तुलना करें",
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
      uploadRetry: "Envoi interrompu — vérifiez la connexion et réessayez.",
      roomView: "Voir",
      roomSub: "Votre pièce",
      takePhoto: "Prendre ou envoyer une photo",
      tryOn: "Voir sur ma photo",
      thinking: "Je réfléchis…",
      tailoring: "J'habille votre %s…",
      pieceWord: { sofa: "canapé", armchair: "fauteuil", curtains: "rideaux", cushions: "coussins" },
      stepDetect: "Je délimite la zone du tissu",
      stepApply: "J'habille votre meuble",
      stepCheck: "Je vérifie le résultat",
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
      steps: { photo: "Je prépare votre photo…", search: "J'examine les 80 tissus…", claw: "Je vérifie la sécurité enfants et animaux…", details: "Je choisis les 3 meilleurs…", room: "J'observe votre pièce…" },
      thinkingNote: "Je réfléchis…",
      snag: { low: "Résistant aux griffes", medium: "Risque moyen", high: "Risque élevé", unknown: "N/A" },
      pieceYou: { sofa: "canapé", armchair: "fauteuil", curtains: "rideaux", cushions: "coussins" },
      stepRetry: "J'ajuste l'application",
      tryAgain: "Réessayer",
      followSwap: "C'est ravissant chez vous. Voir le tissu suivant, ou estimer le métrage ?",
      emptyLeadOptions: "Dites-moi — lequel vous convient ?",
      emptyLeadRecs: "Voici mes meilleurs choix :",
      emptyLeadGeneric: "Pouvez-vous m'en dire un peu plus ?",
      viewAgain: "Revoir",
      rephoto: "Essayer sur une autre photo",
      previewsTitle: "Vos aperçus",
      crumbHome: "Accueil",
      crumbConsult: "Consultation",
      newConsult: "Nouvelle consultation",
      onlineNow: "En ligne · répond dans votre langue",
      canvasEmpty: "Déposez une photo de votre canapé ou fauteuil",
      uploadPhoto: "Envoyer",
      trySample: "Ou essayez une pièce type :",
      sampleLiving: "Salon",
      sampleMajlis: "Majlis",
      sampleArmchair: "Fauteuil",
      holdBefore: "Maintenez pour avant",
      previewing: "Aperçu en cours",
      compareSide: "Comparer côte à côte",
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
      uploadRetry: "No se pudo subir — revisa tu conexión e inténtalo de nuevo.",
      roomView: "Ver",
      roomSub: "Tu espacio",
      takePhoto: "Toma o sube una foto",
      tryOn: "Ver en mi foto",
      thinking: "Pensando…",
      tailoring: "Vistiendo tu %s…",
      pieceWord: { sofa: "sofá", armchair: "sillón", curtains: "cortinas", cushions: "cojines" },
      stepDetect: "Delimito la zona de la tela",
      stepApply: "Visto tu mueble",
      stepCheck: "Compruebo el resultado",
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
      steps: { photo: "Preparando tu foto…", search: "Reviso las 80 telas…", claw: "Compruebo la seguridad para niños y mascotas…", details: "Elijo las 3 mejores…", room: "Miro tu espacio…" },
      thinkingNote: "Estoy pensando…",
      snag: { low: "Resistente a garras", medium: "Riesgo medio", high: "Riesgo alto", unknown: "N/D" },
      pieceYou: { sofa: "sofá", armchair: "sillón", curtains: "cortinas", cushions: "cojines" },
      stepRetry: "Ajusto la aplicación",
      tryAgain: "Reintentar",
      followSwap: "Se ve precioso en tu espacio. ¿Vemos la siguiente tela o calculo los metros?",
      emptyLeadOptions: "Dime — ¿cuál te conviene?",
      emptyLeadRecs: "Estas son mis mejores opciones:",
      emptyLeadGeneric: "¿Me cuentas un poco más lo que necesitas?",
      viewAgain: "Ver de nuevo",
      rephoto: "Probar en otra foto",
      previewsTitle: "Tus vistas previas",
      crumbHome: "Inicio",
      crumbConsult: "Consulta",
      newConsult: "Nueva consulta",
      onlineNow: "En línea · responde en tu idioma",
      canvasEmpty: "Suelta una foto de tu sofá o sillón",
      uploadPhoto: "Subir",
      trySample: "O prueba un salón de muestra:",
      sampleLiving: "Salón",
      sampleMajlis: "Majlis",
      sampleArmchair: "Sillón",
      holdBefore: "Mantén para ver el antes",
      previewing: "Vista previa",
      compareSide: "Comparar lado a lado",
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
    pendingSwap: null,
    pendingSwapLabel: null,
    canvasView: null,
    lastSwap: null
  };

  var $ = function (id) { return document.getElementById(id); };
  var messagesEl, chipsEl, recsEl, composerInput;

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
    state.pendingSwap = null;
    state.pendingSwapLabel = null;
    state.canvasView = null;
    state.lastSwap = null;
    messagesEl.innerHTML = "";
    recsEl.innerHTML = "";
    renderStrip();
    renderCanvas();
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
    if (key === "thinking") return t("thinking");
    return key;
  }

  function pendingScope() {
    return document.getElementById("pending");
  }

  function showStep(key) {
    var scope = pendingScope();
    var el = scope && scope.querySelector(".agent-step");
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
      '<div dir="auto"><div class="agent-step"></div>' +
      '<span class="typing pdots"><span></span><span></span><span></span></span>' +
      '<span class="ptext"></span></div>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    showStep("thinking");
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
    var pending = pendingScope();
    if (!pending) return null;
    var step = pending.querySelector(".agent-step");
    if (step) step.remove();
    var dots = pending.querySelector(".pdots");
    if (dots) dots.remove();
    var body = pending.querySelector(".ptext");
    var fellBack = false;
    var text = (reply && reply.trim()) ? reply :
      (body && body.textContent && body.textContent.trim() ?
        body.textContent : null);
    if (!text) {
      text = t("emptyLeadGeneric");
      fellBack = true;
    }
    if (body) body.innerHTML = formatReply(text);
    if (fellBack) pending.setAttribute("data-fell-back", "1");
    pending.removeAttribute("id");
    return pending;
  }

  function ensureBubbleText(res) {
    var bubbles = messagesEl.querySelectorAll(".msg.them");
    if (!bubbles.length) {
      addMsg(leadIn(res), "them");
      return;
    }
    var last = bubbles[bubbles.length - 1];
    var empty = !(last.textContent || "").trim();
    if (!empty && !last.hasAttribute("data-fell-back")) return;
    last.removeAttribute("data-fell-back");
    var html = formatReply(leadIn(res));
    var p = last.querySelector(".ptext");
    if (p) {
      p.innerHTML = html;
    } else {
      var d = document.createElement("div");
      d.setAttribute("dir", "auto");
      d.innerHTML = html;
      last.appendChild(d);
    }
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
          err.status = r.status;
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

  function canvasChip(icon, text) {
    return '<span class="canvas-chip"><i data-lucide="' + icon +
      '" aria-hidden="true"></i><span dir="auto">' + esc(text) +
      "</span></span>";
  }

  function renderRoomCard(room, detectedPiece) {
    var box = $("canvasChips");
    if (!box) return;
    if (!room) { box.innerHTML = ""; return; }
    var piece = detectedPiece || (room.furniture || "").split(",")[0] || "";
    var html = "";
    if (piece) html += canvasChip("sofa", piece);
    if (room.light_level) html += canvasChip("sun", room.light_level);
    if (room.style) html += canvasChip("palette", room.style);
    var pal = "";
    (room.wall_colors || []).forEach(function (c) {
      pal += '<span class="swatch-chip" title="' + esc(c.name + " " + c.hex) +
        '" style="background:' + esc(c.hex) + '"></span>';
    });
    if (pal) html += '<span class="canvas-chip pal">' + pal + "</span>";
    box.innerHTML = html;
    box.setAttribute("dir", "auto");
    icons();
  }

  function canvasViewSrc() {
    if (state.canvasView) return state.canvasView;
    if (state.roomPhoto) return "/" + state.roomPhoto.replace(/^\/+/, "");
    return "";
  }

  function renderCrumb() {
    var el = $("crumbPiece");
    if (!el) return;
    el.textContent = state.detectedPiece ||
      (state.lastRoom && state.lastRoom.room_type) || "";
  }

  function renderCanvas() {
    var hasPhoto = !!state.roomPhoto;
    $("canvasEmpty").hidden = hasPhoto;
    $("canvasPhotoWrap").hidden = !hasPhoto;
    if (hasPhoto) $("canvasImg").src = canvasViewSrc();
    var hb = $("holdBefore");
    if (hb) hb.hidden = !(state.canvasView && state.roomPhoto);
    renderCanvasRow();
    renderCrumb();
    renderRoomBar();
  }

  function isNarrow() {
    return window.matchMedia &&
      window.matchMedia("(max-width: 719px)").matches;
  }

  function renderRoomBar() {
    var bar = $("roomBar");
    if (!bar) return;
    if (!state.roomPhoto || !isNarrow()) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    var thumb = state.canvasView ||
      "/" + state.roomPhoto.replace(/^\/+/, "");
    if ($("roomThumb").getAttribute("src") !== thumb) {
      $("roomThumb").src = thumb;
    }
    var roomType = (state.lastRoom && (state.lastRoom.room_type || "")) ||
      state.detectedPiece || "";
    var title, sub;
    if (state.lastSwap && state.lastSwap.meta) {
      var m = state.lastSwap.meta;
      title = state.lang === "ar" ? (m.name_ar || m.code)
                                  : (m.name_en || m.code);
      sub = roomType;
    } else {
      title = t("roomSub");
      sub = roomType;
    }
    $("roomFabric").textContent = title;
    var subEl = $("roomSub");
    if (sub && sub !== title) {
      subEl.textContent = sub;
      subEl.hidden = false;
    } else {
      subEl.hidden = true;
    }
  }

  function openSheet() {
    if (!isNarrow()) return;
    document.body.classList.add("sheet-open");
    renderCanvas();
    var sc = $("sheetClose");
    if (sc) sc.setAttribute("aria-label", t("closeLabel"));
  }

  function closeSheet() {
    document.body.classList.remove("sheet-open");
  }

  function renderWelcome() {
    if (!isNarrow() || state.roomPhoto) return;
    if ($("welcomeMsg")) return;
    var div = document.createElement("div");
    div.className = "msg them";
    div.id = "welcomeMsg";
    div.innerHTML = AVATAR + '<div dir="auto"><div class="sample-row">' +
      '<button type="button" data-sample="living"><img src="/data/samples/living.jpg" alt="living"><span>' + esc(t("sampleLiving")) + "</span></button>" +
      '<button type="button" data-sample="majlis"><img src="/data/samples/majlis.jpg" alt="majlis"><span>' + esc(t("sampleMajlis")) + "</span></button>" +
      '<button type="button" data-sample="armchair"><img src="/data/samples/armchair.jpg" alt="armchair"><span>' + esc(t("sampleArmchair")) + "</span></button>" +
      "</div>" +
      '<button type="button" class="seeit" data-upload="1"><i data-lucide="camera" aria-hidden="true"></i><span>' + esc(t("takePhoto")) + "</span></button></div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    icons();
  }

  function canvasStepLabel(key) {
    if (key === "retry") return t("stepRetry");
    var n = SWAP_STEP[key];
    if (n === 0) return t("stepDetect");
    if (n === 1) return t("stepApply");
    if (n === 2) return t("stepCheck");
    return t("stepDetect");
  }

  function renderCanvasRow() {
    var row = $("canvasRow");
    if (!row) return;
    var recs = (state.lastRecs || []).slice(0, 3);
    if (!state.roomPhoto || !recs.length) {
      row.hidden = true;
      row.innerHTML = "";
      return;
    }
    row.hidden = false;
    row.innerHTML = recs.map(function (r) {
      var name = state.lang === "ar" ? r.name_ar : r.name_en;
      var running = state.pendingSwap === r.code;
      var done = !!(state.swaps[r.code] && state.swaps[r.code].result_url);
      var status = running ? (state.pendingSwapLabel || t("stepDetect")) :
        done ? t("previewing") : t("seeIt");
      var cls = "ccard" + (done ? " previewing" : "") +
        (running ? " running" : "");
      return '<button type="button" class="' + cls + '" data-code="' +
        esc(r.code) + '">' +
        '<img src="/' + esc(r.image) + '" alt="' + esc(name) + '">' +
        '<span class="cc-t"><span class="cc-n" dir="auto">' + esc(name) +
        '</span><span class="cc-m">' + esc(r.code) + " · " +
        esc(formatPrice(r.price_sar_per_m)) + "</span>" +
        '<span class="cc-s">' + esc(status) + "</span></span></button>";
    }).join("");
    icons();
  }

  function loadSample(id) {
    if (["living", "majlis", "armchair"].indexOf(id) < 0) return;
    fetch("/data/samples/" + id + ".jpg")
      .then(function (r) {
        if (!r.ok) throw new Error("sample");
        return r.blob();
      })
      .then(function (blob) {
        upload(new File([blob], id + ".jpg", { type: "image/jpeg" }));
      })
      .catch(function () { addMsg(t("uploadFail"), "them"); });
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

  function miniRecsHTML(recs) {
    return '<div class="mini-recs">' + recs.map(function (r) {
      var name = state.lang === "ar" ? r.name_ar : r.name_en;
      return '<div class="mini-card" data-fabric="' + esc(r.code) +
        '" role="button" tabindex="0">' +
        '<img src="/' + esc(r.image) + '" alt="' + esc(name) +
        '" loading="lazy">' +
        '<div class="mini-n" dir="auto">' + esc(name) + "</div>" +
        '<div class="mini-m">' + esc(r.code) + " · " +
        esc(formatPrice(r.price_sar_per_m)) + "</div>" +
        '<button type="button" class="seeit mini-try" data-try="' +
        esc(r.code) + '"><span>' + esc(t("tryOn")) + "</span></button>" +
        "</div>";
    }).join("") + "</div>";
  }

  function appendRecsToChat(recs) {
    var div = document.createElement("div");
    div.className = "msg them recs-msg";
    div.innerHTML = AVATAR + '<div dir="auto">' + miniRecsHTML(recs) +
      "</div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    icons();
    return div;
  }

  function showRecs(recs) {
    if (!recs || !recs.length) return;
    if (isNarrow()) appendRecsToChat(recs);
    else renderRecs(recs);
  }

  function maybeAutoPreview(res) {
    if (res && res.preview && res.preview.code) {
      var opts = {};
      if (res.preview.target) opts.target = res.preview.target;
      openSwap(res.preview.code, opts);
    }
  }

  function handleResult(res) {
    autoLang(res);
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    if (res.recommendations && res.recommendations.length) {
      state.lastRecs = res.recommendations;
    }
    state.lastOptions = res.options || [];
    if (res.room_analysis) state.lastRoom = res.room_analysis;
    if (res.detected_piece) state.lastDetected = res.detected_piece;
    renderRoomCard(state.lastRoom, state.lastDetected);
    renderCanvas();
    addMsg(leadIn(res), "them");
    if (state.lastRecs && state.lastRecs.length) showRecs(state.lastRecs);
    if (state.lastOptions && state.lastOptions.length) renderOptions(state.lastOptions);
    maybeAutoPreview(res);
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

  var SWAP_TARGETS = ["sofa", "armchair", "curtains", "cushions"];

  function tryFabric(code) {
    if (!state.roomPhoto) {
      if (isNarrow()) {
        openSheet();
      } else {
        addMsg(t("needPhoto"), "them");
        var dz = $("dropzone");
        dz.scrollIntoView({ behavior: "smooth", block: "center" });
        dz.classList.add("flash");
        setTimeout(function () { dz.classList.remove("flash"); }, 1600);
      }
      return;
    }
    openSwap(code);
  }

  function fabricSheetRec(code) {
    var list = state.lastRecs || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].code === code) return list[i];
    }
    return null;
  }

  function openFabricSheet(code) {
    var r = fabricSheetRec(code);
    if (!r) return;
    var name = state.lang === "ar" ? r.name_ar : r.name_en;
    var feats = (r.features || []).map(function (f) {
      return '<span class="feat"><i data-lucide="' +
        (FEATURE_ICONS[f] || "sparkles") +
        '" aria-hidden="true"></i> ' + esc(featLabel(f)) + "</span>";
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
    $("fabricSheetBody").innerHTML =
      '<div class="swatch big"><img src="/' + esc(r.image) + '" alt="' +
      esc(name) + '"><span class="code-pill">' + esc(r.code) + "</span></div>" +
      '<div class="body" dir="auto"><div class="name">' + esc(name) + "</div>" +
      '<div class="meta"><i data-lucide="ruler" aria-hidden="true"></i><span>' +
      esc(formatPrice(r.price_sar_per_m)) + "</span></div>" +
      (r.reason ? '<p class="why">' + esc(r.reason) + "</p>" : "") +
      '<div class="featrow">' + feats +
      '<span class="' + snagClass(r.snag_risk) + '">' +
      esc(t("snag")[r.snag_risk] || r.snag_risk) + "</span></div>" +
      receipts + "</div>";
    var btn = $("fabricTry");
    btn.setAttribute("data-try", r.code);
    btn.querySelector("span").textContent = t("tryOn");
    $("fabricSheet").hidden = false;
    document.body.classList.add("modal-open");
    icons();
  }

  function closeFabricSheet() {
    $("fabricSheet").hidden = true;
    if ($("swapModal").hidden) document.body.classList.remove("modal-open");
  }

  function openSwap(code, opts) {
    opts = opts || {};
    closeFabricSheet();
    if (!state.roomPhoto && !opts.review) {
      tryFabric(code);
      return;
    }
    state.swapCode = code;
    state.swapRetried = !!opts.noRetry;
    var target = SWAP_TARGETS.indexOf(opts.target) >= 0 ?
      opts.target : swapTarget();
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
    state.pendingSwap = code;
    state.pendingSwapLabel = t("stepDetect");
    renderCanvasRow();
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
            state.pendingSwapLabel = canvasStepLabel(evt.label);
            renderCanvasRow();
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
            state.pendingSwap = null;
            state.pendingSwapLabel = null;
            renderCanvasRow();
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
    state.pendingSwap = null;
    state.pendingSwapLabel = null;
    state.canvasView = "/" + (res.result_url || "").replace(/^\/+/, "");
    renderStrip();
    renderCanvas();
    postSwapMessage(entry);
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
    var cmp = $("compareBtn");
    if (cmp) cmp.hidden = state.prevList.length < 2;
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
            var scope = pendingScope();
            var pText = scope && scope.querySelector(".ptext");
            var pDots = scope && scope.querySelector(".pdots");
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
      var scope = pendingScope();
      var body = scope && scope.querySelector(".ptext");
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
    if (res.recommendations && res.recommendations.length) {
      state.lastRecs = res.recommendations;
    }
    state.lastOptions = res.options || [];
    if (res.room_analysis) state.lastRoom = res.room_analysis;
    if (res.detected_piece) state.lastDetected = res.detected_piece;
    renderRoomCard(state.lastRoom, state.lastDetected);
    renderCanvas();
    ensureBubbleText(res);
    if (state.lastRecs && state.lastRecs.length) {
      showRecs(state.lastRecs);
    }
    if (state.lastOptions && state.lastOptions.length) {
      renderOptions(state.lastOptions);
    }
    maybeAutoPreview(res);
  }

  function preparePhoto(file) {
    if (typeof createImageBitmap === "undefined") {
      return Promise.resolve(file);
    }
    var decoded = null;
    try {
      decoded = createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (e) {
      decoded = null;
    }
    if (!decoded || !decoded.then) {
      try {
        decoded = createImageBitmap(file);
      } catch (e) {
        return Promise.resolve(file);
      }
    }
    function canvasToJpeg(canvas) {
      function viaDataURL() {
        try {
          var parts = canvas.toDataURL("image/jpeg", 0.85).split(",");
          var bin = atob(parts[1]);
          var arr = new Uint8Array(bin.length);
          for (var i = 0; i < bin.length; i++) {
            arr[i] = bin.charCodeAt(i);
          }
          return new Blob([arr], { type: "image/jpeg" });
        } catch (e) {
          return null;
        }
      }
      return new Promise(function (resolve) {
        if (canvas.toBlob) {
          try {
            canvas.toBlob(function (blob) {
              resolve(blob || viaDataURL() || file);
            }, "image/jpeg", 0.85);
            return;
          } catch (e) {}
        }
        resolve(viaDataURL() || file);
      });
    }
    return decoded.then(function (bmp) {
      var w = bmp.width, h = bmp.height;
      if (!w || !h) return file;
      var scale = Math.min(1, 2048 / Math.max(w, h));
      var canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(w * scale));
      canvas.height = Math.max(1, Math.round(h * scale));
      canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width,
                                        canvas.height);
      if (bmp.close) bmp.close();
      return canvasToJpeg(canvas);
    }).catch(function () {
      return file;
    });
  }

  function upload(file) {
    var fd = new FormData();
    var usePreview = URL.createObjectURL(file);
    addMsg("", "me", usePreview);
    chipsEl.hidden = true;
    state.booted = true;
    // One live bubble for the whole photo turn: every backend stage
    // reports into it via SSE step events, then tokens stream in.
    pendingBubble();
    showStep("photo");
    var savedPath = null;
    preparePhoto(file).then(function (ready) {
      fd.append("file", ready,
                ready === file ? (file.name || "photo.jpg") : "photo.jpg");
      return fetchReq("/api/upload", { form: fd, timeoutMs: 60000,
                                      retries: 1 });
    })
      .then(function (data) {
        // Room state only commits once the follow-up chat confirms the
        // photo: a chat failure must never leave a broken canvas behind.
        savedPath = data.image_path;
        // Warm the item targets while the chat runs: detection and SAM
        // are independent of the conversation, so the sheet opens ready.
        fetchReq("/api/session/" + encodeURIComponent(state.sessionId) +
                 "/targets?image_path=" + encodeURIComponent(savedPath),
                 { method: "GET", timeoutMs: 120000, retries: 0 })
          .catch(function () {});
        return streamChat("", savedPath);
      })
      .then(function (res) {
        if (!res) {
          dropPending();
          return;
        }
        if (res.fallback && res.reply) finalizePending(res.reply);
        state.roomPhoto = savedPath;
        state.canvasView = null;
        handleStreamResult(res);
        if (state.expectFirst === "sample") {
          state.expectFirst = null;
          chipsEl.hidden = false;
        }
        if (state.pendingSwapCode) {
          var code = state.pendingSwapCode;
          state.pendingSwapCode = null;
          openSwap(code);
        }
      })
      .catch(function (err) {
        dropPending();
        state.expectFirst = null;
        state.roomPhoto = null;
        state.canvasView = null;
        renderCanvas();
        if (typeof console !== "undefined" && console.error) {
          console.error("upload failed",
                        err && (err.status || err.message));
        }
        var key = savedPath ? "sendFail"
          : (err && err.status === 400 ? "uploadFail" : "uploadRetry");
        addMsg(t(key), "them");
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
    $("photoBtn").addEventListener("click", function () { fi.click(); });
    $("uploadBtn").addEventListener("click", function () { fi.click(); });
    $("newConsult").addEventListener("click", function () {
      setLang(state.lang, true);
    });
    document.addEventListener("click", function (e) {
      var s = e.target && e.target.closest ?
        e.target.closest("[data-sample]") : null;
      if (s && s.dataset.sample) loadSample(s.dataset.sample);
      var up = e.target && e.target.closest ?
        e.target.closest("[data-upload]") : null;
      if (up) fi.click();
      var tryBtn = e.target && e.target.closest ?
        e.target.closest("[data-try]") : null;
      if (tryBtn && tryBtn.dataset.try) {
        tryFabric(tryBtn.dataset.try);
        return;
      }
      var fab = e.target && e.target.closest ?
        e.target.closest("[data-fabric]") : null;
      if (fab && fab.dataset.fabric) openFabricSheet(fab.dataset.fabric);
      var card = e.target && e.target.closest ?
        e.target.closest("#canvasRow .ccard") : null;
      if (card && card.dataset.code) openSwap(card.dataset.code);
    });
    $("compareBtn").addEventListener("click", function () {
      var list = state.prevList || [];
      if (list.length < 2) return;
      var a = list[list.length - 2], b = list[list.length - 1];
      if (state.compareSel.length >= 2) {
        a = list[state.compareSel[0]];
        b = list[state.compareSel[1]];
      }
      if (a && b) openSwapCompare(a, b);
    });
    (function holdBefore() {
      var btn = $("holdBefore");
      if (!btn) return;
      var downAt = 0, pinned = false;
      function showBefore(on) {
        var img = $("canvasImg");
        if (!img || !state.roomPhoto) return;
        img.src = on ? "/" + state.roomPhoto.replace(/^\/+/, "")
                     : canvasViewSrc();
      }
      btn.addEventListener("pointerdown", function () {
        downAt = Date.now();
        pinned = false;
        showBefore(true);
      });
      ["pointerup", "pointerleave", "pointercancel"].forEach(function (ev) {
        btn.addEventListener(ev, function () {
          if (Date.now() - downAt < 300) {
            pinned = !pinned;
            showBefore(pinned);
          } else if (!pinned) {
            showBefore(false);
          }
        });
      });
    })();
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
    $("fabricClose").addEventListener("click", closeFabricSheet);
    $("fabricSheet").addEventListener("click", function (e) {
      if (e.target === $("fabricSheet")) closeFabricSheet();
    });
    document.addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === " ") && e.target &&
          e.target.closest) {
        var kf = e.target.closest("[data-fabric]");
        if (kf && kf.dataset.fabric && !e.target.closest("[data-try]")) {
          e.preventDefault();
          openFabricSheet(kf.dataset.fabric);
        }
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("swapModal").hidden) closeSwap();
      else if (e.key === "Escape" && !$("fabricSheet").hidden) closeFabricSheet();
      else if (e.key === "Escape" &&
        document.body.classList.contains("sheet-open")) closeSheet();
    });
    function fitAppHeight() {
      var h = (window.visualViewport && window.visualViewport.height) ||
        window.innerHeight;
      document.documentElement.style.setProperty(
        "--app-height", Math.round(h) + "px");
    }
    fitAppHeight();
    window.addEventListener("resize", fitAppHeight);
    window.addEventListener("orientationchange", fitAppHeight);
    document.addEventListener("scroll", fitAppHeight, { passive: true });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", fitAppHeight);
    }
    $("roomView").addEventListener("click", openSheet);
    $("roomThumbBtn").addEventListener("click", openSheet);
    $("roomThumb").addEventListener("error", function () {
      var bar = $("roomBar");
      if (bar) bar.hidden = true;
    });
    $("sheetClose").addEventListener("click", closeSheet);
    (function sheetSwipe() {
      var pane = document.querySelector(".canvas-pane");
      if (!pane) return;
      var y0 = null;
      pane.addEventListener("touchstart", function (e) {
        y0 = e.touches[0].clientY;
      }, { passive: true });
      pane.addEventListener("touchend", function (e) {
        if (y0 === null) return;
        var dy = e.changedTouches[0].clientY - y0;
        y0 = null;
        if (dy > 90 && e.changedTouches[0].clientY < 220) closeSheet();
      });
    })();

    renderCanvas();
    var sample = new URLSearchParams(location.search).get("sample");
    var hasSample = ["living", "majlis", "armchair"].indexOf(sample) >= 0;
    if (hasSample) {
      // The sample photo IS the first turn: it chats with the image, so
      // analyze runs before the first reply. No imageless greeting.
      state.expectFirst = "sample";
      loadSample(sample);
    } else {
      bootGreeting();
    }
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
        renderWelcome();
        fetchPreviews();
      })
      .catch(function () {
        if (sid !== state.sessionId) return;
        typingOff();
        addMsg(t("sendFail"), "them");
        renderWelcome();
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
