/* ReCover chat UI. No build step, vanilla JS. */
(function () {
  "use strict";

  var STRINGS = {
    en: {
      tagline: "Change the look, not the furniture.",
      forYou: "For you",
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
      skipNote: "Couldn't change %s — left as is",
      notApplied: "%s — not applied",
      checkColour: "colour mismatch",
      checkCoverage: "fabric didn't cover the whole item",
      traceChecks: "colour ΔE %s · coverage %s",
      tryOnTarget: "Try on the %s",
      tryWord: { sofa: "sofa", armchair: "armchair", curtains: "curtains", cushions: "cushions" },
      tapToChange: "Tap what you'd like to change",
      allItems: "All",
      recsUnderPhoto: "Your 3 picks are under the photo — tap one to try it.",
      fewQualify: "Only %d fabrics qualified — here they are:",
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
      applyAll: "Apply to all",
      resetPicks: "Reset",
      browseTitle: "Browse fabrics",
      browseFor: "for your %s",
      pickOne: "Pick",
      applyOne: "Apply",
      summaryTitle: "Your picks",
      closeBrowse: "Close",
      meterUnit: "m",
      sarUnit: "SAR",
      totalLabel: "Total",
      sendUpholsterer: "Send to upholsterer",
      tryAnother: "Try another fabric",
      copySummary: "Copy summary",
      copiedTick: "Copied",
      needsMeasure: "needs measurements",
      preliminaryNote: "Preliminary estimate — your upholsterer will measure.",
      co2Line: "By keeping your %s you avoid ≈%d kg CO₂e of new manufacturing and ≈%d kg of furniture waste",
      co2Source: "Source: EPD NEPD-1805-759",
      co2Note: "Based on one published EPD (A1–A3 manufacturing stages).",
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
      sampleCurtains: "Curtains",
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
      swapTimeout: "The preview timed out — the model is slow right now. Tap Try again.",
      underHood: "Under the hood",
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
      skipNote: "ما قدرنا نغيّر %s — خلّيناه زي ما هو",
      notApplied: "%s — ما تركّب",
      checkColour: "اللون ما طابق",
      checkCoverage: "القماش ما غطّى القطعة كاملة",
      traceChecks: "اللون ΔE %s · التغطية %s",
      tryOnTarget: "جرّبه على %s",
      tryWord: { sofa: "الكنبة", armchair: "الكرسي", curtains: "الستائر", cushions: "المخدات" },
      tapToChange: "اضغط على اللي ودك تغّيره",
      allItems: "الكل",
      recsUnderPhoto: "اختياراتك الثلاثة تحت الصورة — اضغط على واحد لتجربته.",
      fewQualify: "بس %d أقمشة تناسب — هذي هي:",
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
      swapTimeout: "المعاينة طولت — النموذج بطيء الحين. اضغط حاول مرة ثانية.",
      underHood: "تحت الغطاء",
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
      applyAll: "طبّق على الكل",
      resetPicks: "إعادة",
      browseTitle: "تصفح الأقمشة",
      browseFor: "لـ%s",
      pickOne: "اختر",
      applyOne: "طبّق",
      summaryTitle: "اختياراتك",
      closeBrowse: "إغلاق",
      meterUnit: "م",
      sarUnit: "ر.س",
      totalLabel: "الإجمالي",
      sendUpholsterer: "أرسل للمنجّد",
      tryAnother: "جرّب قماش ثاني",
      copySummary: "انسخ الملخص",
      copiedTick: "تم النسخ",
      needsMeasure: "يحتاج مقاسات",
      preliminaryNote: "تقدير مبدئي — المقاس النهائي من المنجّد.",
      co2Line: "باحفاظك على %s تتجنّب ≈%d كغ CO₂e من التصنيع الجديد و≈%d كغ من نفايات الأثاث",
      co2Source: "المصدر: EPD NEPD-1805-759",
      co2Note: "مبني على إعلان بيئي واحد منشور (مراحل التصنيع A1–A3).",
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
      sampleCurtains: "ستائر",
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
      skipNote: "%s नहीं बदल पाए — जैसा है वैसा रखा",
      notApplied: "%s — लागू नहीं हुआ",
      checkColour: "रंग मेल नहीं खाया",
      checkCoverage: "कपड़े ने पूरा हिस्सा नहीं ढका",
      traceChecks: "रंग ΔE %s · कवरेज %s",
      tryOnTarget: "%s पर आज़माएँ",
      tryWord: { sofa: "सोफ़ा", armchair: "कुर्सी", curtains: "परदे", cushions: "तकिए" },
      tapToChange: "जो बदलना है उस पर दबाएँ",
      allItems: "सभी",
      recsUnderPhoto: "आपके 3 सुझाव फ़ोटो के नीचे हैं — आज़माने के लिए एक पर दबाएँ।",
      fewQualify: "सिर्फ़ %d कपड़े सही बैठे — ये रहे:",
      applyAll: "सब पर लागू करें",
      resetPicks: "रीसेट",
      browseTitle: "कपड़े देखें",
      browseFor: "%s के लिए",
      pickOne: "चुनें",
      applyOne: "लागू करें",
      summaryTitle: "आपकी पसंद",
      closeBrowse: "बंद करें",
      meterUnit: "मी",
      sarUnit: "SAR",
      totalLabel: "कुल",
      sendUpholsterer: "मिस्त्री को भेजें",
      tryAnother: "दूसरा कपड़ा आज़माएँ",
      copySummary: "सारांश कॉपी करें",
      copiedTick: "कॉपी हुआ",
      needsMeasure: "नाप चाहिए",
      preliminaryNote: "शुरुआती अंदाज़ा — आखिरी नाप मिस्त्री लेगा।",
      co2Line: "अपने %s को रखकर आप ≈%d kg CO₂e नए उत्पादन और ≈%d kg फ़र्नीचर कचरे से बचते हैं",
      co2Source: "स्रोत: EPD NEPD-1805-759",
      co2Note: "एक प्रकाशित EPD पर आधारित (A1–A3 उत्पादन चरण)।",
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
      swapTimeout: "झलक में समय लग गया — मॉडल अभी धीमा है। फिर कोशिश करें दबाएँ।",
      underHood: "परदे के पीछे",
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
      sampleCurtains: "परदे",
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
      skipNote: "Impossible de changer %s — laissé tel quel",
      notApplied: "%s — non appliqué",
      checkColour: "couleur non conforme",
      checkCoverage: "le tissu n'a pas couvert toute la pièce",
      traceChecks: "couleur ΔE %s · couverture %s",
      tryOnTarget: "Essayer sur %s",
      tryWord: { sofa: "canapé", armchair: "fauteuil", curtains: "rideaux", cushions: "coussins" },
      tapToChange: "Touchez ce que vous voulez changer",
      allItems: "Tout",
      recsUnderPhoto: "Vos 3 choix sont sous la photo — touchez-en un pour l'essayer.",
      fewQualify: "Seuls %d tissus conviennent — les voici :",
      applyAll: "Tout appliquer",
      resetPicks: "Réinitialiser",
      browseTitle: "Parcourir les tissus",
      browseFor: "pour votre %s",
      pickOne: "Choisir",
      applyOne: "Appliquer",
      summaryTitle: "Vos choix",
      closeBrowse: "Fermer",
      meterUnit: "m",
      sarUnit: "SAR",
      totalLabel: "Total",
      sendUpholsterer: "Envoyer au tapissier",
      tryAnother: "Essayer un autre tissu",
      copySummary: "Copier le résumé",
      copiedTick: "Copié",
      needsMeasure: "mesures requises",
      preliminaryNote: "Estimation préliminaire — votre tapissier prendra les mesures.",
      co2Line: "En gardant votre %s vous évitez ≈%d kg de CO₂e de fabrication neuve et ≈%d kg de déchets de meubles",
      co2Source: "Source : EPD NEPD-1805-759",
      co2Note: "Basé sur une EPD publiée (étapes de fabrication A1–A3).",
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
      swapTimeout: "L'aperçu a expiré — le modèle est lent pour le moment. Touchez Réessayer.",
      underHood: "En coulisses",
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
      sampleCurtains: "Rideaux",
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
      skipNote: "No se pudo cambiar %s — se dejó como estaba",
      notApplied: "%s — no aplicado",
      checkColour: "color no coincide",
      checkCoverage: "la tela no cubrió toda la pieza",
      traceChecks: "color ΔE %s · cobertura %s",
      tryOnTarget: "Probar en %s",
      tryWord: { sofa: "sofá", armchair: "sillón", curtains: "cortinas", cushions: "cojines" },
      tapToChange: "Toca lo que quieras cambiar",
      allItems: "Todo",
      recsUnderPhoto: "Tus 3 opciones están bajo la foto — toca una para probarla.",
      fewQualify: "Solo %d telas sirven — aquí están:",
      applyAll: "Aplicar a todo",
      resetPicks: "Restablecer",
      browseTitle: "Ver telas",
      browseFor: "para tu %s",
      pickOne: "Elegir",
      applyOne: "Aplicar",
      summaryTitle: "Tus elecciones",
      closeBrowse: "Cerrar",
      meterUnit: "m",
      sarUnit: "SAR",
      totalLabel: "Total",
      sendUpholsterer: "Enviar al tapicero",
      tryAnother: "Probar otra tela",
      copySummary: "Copiar resumen",
      copiedTick: "Copiado",
      needsMeasure: "faltan medidas",
      preliminaryNote: "Estimación preliminar — tu tapicero tomará las medidas.",
      co2Line: "Al conservar tu %s evitas ≈%d kg de CO₂e de fabricación nueva y ≈%d kg de residuos de muebles",
      co2Source: "Fuente: EPD NEPD-1805-759",
      co2Note: "Basado en una EPD publicada (etapas de fabricación A1–A3).",
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
      swapTimeout: "La vista tardó demasiado — el modelo está lento ahora. Toca Reintentar.",
      underHood: "Entre bastidores",
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
      sampleCurtains: "Cortinas",
      holdBefore: "Mantén para ver el antes",
      previewing: "Vista previa",
      compareSide: "Comparar lado a lado",
      previewsHint: "Toca una para ver, dos para comparar",
      features: {},
      matched: {},
      relaxed: {}
    }
  };

  var LANG_INDEX = { en: 0, ar: 1, hi: 2, fr: 3, es: 4 };

  function langLabel(pair) {
    var i = LANG_INDEX[state.lang];
    if (i === undefined) i = 0;
    return pair[i] !== undefined ? pair[i] : pair[0];
  }

  var FEATURE_LABELS = {
    "fire-resistant": ["Fire-resistant", "مقاوم للحريق", "आग-रोधी", "Ignifugé", "Ignífugo"],
    "easy-clean": ["Easy-clean", "سهل التنظيف", "आसान-सफ़ाई", "Facile d'entretien", "Fácil de limpiar"],
    "washable": ["Washable", "قابل للغسل", "धोने योग्य", "Lavable", "Lavable"],
    "stain-resistant": ["Stain-resistant", "مقاوم للبقع", "दाग-रोधी", "Antitache", "Antimanchas"],
    "antibacterial": ["Antibacterial", "مضاد للبكتيريا", "जीवाणुरोधी", "Antibactérien", "Antibacteriano"],
    "pet-friendly": ["Pet-friendly", "مناسب للحيوانات", "पालतू-मित्रवत", "Animaux admis", "Apto para mascotas"],
    "scratch-resistant": ["Scratch-resistant", "مقاوم للخدش", "खरोंच-रोधी", "Résistant aux griffes", "Resistente a arañazos"],
    "fade-resistant": ["Fade-resistant", "مقاوم للبهتان", "रंग-टिकाऊ", "Résistant à la décoloration", "Resistente a la decoloración"],
    "crease-resistant": ["Crease-resistant", "مقاوم للتجعد", "सिलवट-रोधी", "Infroissable", "Antiarrugas"],
    "blackout": ["Blackout", "تعتيم كامل", "ब्लैकआउट", "Occultant", "Opaco"],
    "thermal-insulating": ["Thermal", "عازل حراري", "थर्मल", "Thermique", "Térmico"],
    "sound-absorbing": ["Sound-absorbing", "ماص للصوت", "ध्वनि-अवशोषक", "Absorbant acoustique", "Absorbente acústico"],
    "hypoallergenic": ["Hypoallergenic", "مضاد للحساسية", "हाइपोएलर्जेनिक", "Hypoallergénique", "Hipoalergénico"],
    "eco-friendly": ["Eco-friendly", "صديق للبيئة", "पर्यावरण-मित्र", "Écologique", "Ecológico"],
    "under-budget": ["Under budget", "ضمن الميزانية", "बजट के अंदर", "Dans le budget", "Dentro del presupuesto"],
    "warm-tone": ["Warm tone", "درجة دافئة", "गर्म रंग", "Ton chaud", "Tono cálido"],
    "cool-tone": ["Cool tone", "درجة باردة", "ठंडा रंग", "Ton froid", "Tono frío"],
    "neutral-tone": ["Neutral tone", "درجة محايدة", "तटस्थ रंग", "Ton neutre", "Tono neutro"]
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
    "max_price": ["Budget", "الميزانية", "बजट", "Budget", "Presupuesto"],
    "features": ["Fabric features", "مواصفات القماش", "कपड़े की खूबियाँ", "Caractéristiques", "Características"],
    "any_features": ["Pet protection", "الحماية من الحيوانات", "पालतू सुरक्षा", "Protection animaux", "Protección mascotas"],
    "snag_levels": ["Claw-safe weave", "قماش آمن من الخدش", "पंजा-सुरक्षित बुनाई", "Tissu anti-griffes", "Tejido antirrasguños"],
    "min_martindale": ["Durability", "المتانة", "टिकाऊपन", "Durabilité", "Durabilidad"],
    "colors": ["Colors", "الألوان", "रंग", "Couleurs", "Colores"],
    "tone": ["Color tone", "درجة اللون", "रंगत", "Ton", "Tono"],
    "styles": ["Style", "الستايل", "स्टाइल", "Style", "Estilo"],
    "suitable_for": ["Intended use", "الاستخدام المقصود", "उपयोग", "Usage prévu", "Uso previsto"],
    "plain_or_patterned": ["Pattern", "النقشة", "डिज़ाइन", "Motif", "Estampado"],
    "opacity": ["Curtain opacity", "تعتيم الستارة", "परदे की ओपेसिटी", "Opacité", "Opacidad"],
    "usage": ["Fabric use", "استخدام القماش", "कपड़े का उपयोग", "Usage", "Uso"]
  };

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && STRINGS[q]) return q;
    // A7/A6: carry the language picked on the landing page.
    try {
      var saved = window.localStorage.getItem("recover_lang");
      if (saved && STRINGS[saved]) return saved;
    } catch (e) {}
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
    swapSeq: 0,
    swapController: null,
    canvasView: null,
    lastSwap: null,
    outlines: [],
    assignments: {},
    chosenTargets: [],
    selectedTarget: null,
    browseList: [],
    browseFor: null,
    multiRunning: false
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
    var pair = FEATURE_LABELS[k] || [key, key, key, key, key];
    return langLabel(pair);
  }

  function toArabicDigits(value) {
    return String(value).replace(/\d/g, function (d) { return "٠١٢٣٤٥٦٧٨٩"[+d]; });
  }

  function matchBadgeText(match) {
    var text = t("matchBadge").replace("%d", match);
    return state.lang === "ar" ? toArabicDigits(text) : text;
  }

  function formatPrice(sar) {
    if (state.lang === "ar") return toArabicDigits(sar) + " ر.س/م";
    return sar + " " + t("perMeter");
  }

  function notFeatureLabel(key) {
    var label = featLabel(key);
    if (state.lang === "ar") return "مو " + label;
    if (state.lang === "hi") return label + " नहीं";
    if (state.lang === "fr") return "Non " + label.charAt(0).toLowerCase() + label.slice(1);
    if (state.lang === "es") return "No " + label.charAt(0).toLowerCase() + label.slice(1);
    return "Not " + label.charAt(0).toLowerCase() + label.slice(1);
  }

  function budgetPill(rb) {
    var price = rb.price + " SAR/m";
    var over = rb.over;
    if (state.lang === "ar") {
      price = toArabicDigits(rb.price) + " ر.س/م";
      over = toArabicDigits(rb.over);
      return price + " — أعلى من ميزانيتك بـ " + over;
    }
    if (state.lang === "hi") return price + " — बजट से " + over + " ज़्यादा";
    if (state.lang === "fr") return price + " — " + over + " au-dessus du budget";
    if (state.lang === "es") return price + " — " + over + " sobre el presupuesto";
    return price + " — " + over + " over budget";
  }

  function relaxLabel(key) {
    var pair = RELAX_LABELS[key] || [key, key, key, key, key];
    return langLabel(pair);
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
    if (typeof paintStepBadges === "function") paintStepBadges();
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

  function renderActionChips(actions) {
    chipsEl.innerHTML = "";
    (actions || []).forEach(function (a) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "action-chip";
      b.textContent = a.label;
      b.addEventListener("click", a.run);
      chipsEl.appendChild(b);
    });
    chipsEl.hidden = !(actions && actions.length);
  }

  function quoteActions(quote) {
    var target = (quote && quote.target) ||
      (state.chosenTargets || [])[0] || state.selectedTarget || "";
    return [
      { label: t("sendUpholsterer"), run: function () {
          var links = messagesEl.querySelectorAll(".sum-card .sum-actions a");
          var a = links[links.length - 1];
          if (a) { window.open(a.href, "_blank", "noopener"); return; }
          var cards = messagesEl.querySelectorAll(".sum-card");
          var card = cards[cards.length - 1];
          if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
        } },
      { label: t("tryAnother"), run: function () {
          if (isNarrow()) openSheet();
          if (target) openBrowse(target);
        } }
    ];
  }

  function afterQuote(res) {
    // Any quote (single item too): the summary card with meters, SAR
    // total, CO2 and the Send / Copy actions, then action chips.
    if (!res || !res.quote) return false;
    postSummaryCard(null).then(function () {
      renderActionChips(quoteActions(res.quote));
    });
    return true;
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
    state.outlines = [];
    state.assignments = {};
    state.chosenTargets = [];
    state.selectedTarget = null;
    state.pickerThumbs = {};
    state.browseList = [];
    state.browseFor = null;
    state.multiRunning = false;
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

  function showStep(key, model) {
    var scope = pendingScope();
    var el = scope && scope.querySelector(".agent-step");
    if (!el) return;
    el.innerHTML = esc(stepLabel(key)) + modelBadge(model);
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
    renderOutlines();
    renderAssignRow();
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
      '<button type="button" data-sample="curtains"><img src="/data/samples/curtains.jpg" alt="curtains"><span>' + esc(t("sampleCurtains")) + "</span></button>" +
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
      var statusBadge = running ? modelBadge(state.pendingSwapModel)
                                : "";
      var cls = "ccard" + (done ? " previewing" : "") +
        (running ? " running" : "");
      return '<button type="button" class="' + cls + '" data-code="' +
        esc(r.code) + '">' +
        '<img src="/' + esc(r.image) + '" alt="' + esc(name) + '">' +
        '<span class="cc-t"><span class="cc-n" dir="auto">' + esc(name) +
        '</span><span class="cc-m">' + esc(r.code) + " · " +
        esc(formatPrice(r.price_sar_per_m)) + "</span>" +
        '<span class="cc-s">' + esc(status) + statusBadge +
        "</span></span></button>";
    }).join("");
    icons();
  }

  var TARGET_WORDS = {
    sofa: ["sofa", "كنب"],
    armchair: ["armchair", "chair", "كرسي"],
    curtains: ["curtain", "drape", "ستار", "ستائر"],
    cushions: ["cushion", "pillow", "وسا", "مخد", "خداد"]
  };

  function targetLabel(target) {
    var words = t("pieceWord") || {};
    return words[target] || target;
  }

  function optionForTarget(target) {
    var words = TARGET_WORDS[target] || [target];
    var opts = state.lastOptions || [];
    for (var i = 0; i < opts.length; i++) {
      var low = String(opts[i]).toLowerCase();
      for (var j = 0; j < words.length; j++) {
        if (low.indexOf(words[j].toLowerCase()) >= 0) return opts[i];
      }
    }
    return null;
  }

  function allOption() {
    var opts = state.lastOptions || [];
    for (var i = 0; i < opts.length; i++) {
      var low = String(opts[i]).toLowerCase().trim();
      for (var j = 0; j < ALL_WORDS.length; j++) {
        if (low === ALL_WORDS[j] || low.indexOf(ALL_WORDS[j] + " ") === 0) {
          return opts[i];
        }
      }
    }
    return null;
  }

  function selectTarget(id, fromTap) {
    if (id === "all") {
      // Every item: no single swap target; the server expands "All".
      state.selectedTarget = "all";
      renderOutlines();
      renderAssignRow();
      syncPickerSelection("all");
      if (fromTap) send(allOption() || t("allItems"));
      return;
    }
    state.selectedTarget = id;
    renderOutlines();
    renderAssignRow();
    syncPickerSelection(id);
    var bar = $("roomBar");
    if (bar) bar.classList.toggle("sel", !!id);
    if (fromTap) {
      var opt = optionForTarget(id);
      if (opt) send(opt);
      else if ((state.chosenTargets || []).indexOf(id) >= 0) openBrowse(id);
      // No option mentions this item and it is not chosen yet (a
      // restored session, or a turn with no options): the tap IS the
      // choice, so tell the consultant in words.
      else send(targetLabel(id));
    }
  }

  function syncPickerSelection(id) {
    var taps = document.querySelectorAll("[data-outline]");
    for (var i = 0; i < taps.length; i++) {
      var on = taps[i].dataset.outline === id;
      taps[i].classList.toggle("sel", on);
      if (taps[i].classList.contains("item-thumb")) {
        taps[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
    }
    refreshChatPicker();
  }

  function fetchOutlines(again) {
    var path = state.roomPhoto;
    if (!path) return;
    // One in-flight outlines fetch per photo: the upload + canvas-init
    // call sites race, and every duplicate is a full SAM segmentation.
    if (state.outlinesFetching === path) return;
    state.outlinesFetching = path;
    fetchReq("/api/session/" + encodeURIComponent(state.sessionId) +
             "/targets?image_path=" + encodeURIComponent(path),
             { method: "GET", timeoutMs: 180000, retries: 0 })
      .then(function (data) {
        if (state.outlinesFetching === path) state.outlinesFetching = "";
        if (path !== state.roomPhoto) return;
        state.outlines = (data && data.targets) || [];
        renderOutlines();
        renderAssignRow();
        postOutlineMessage();
      }).catch(function () {
        if (state.outlinesFetching === path) state.outlinesFetching = "";
        // One delayed retry: SAM segmentation can outlast the first
        // budget on a cold container. Never loops.
        if (!again) {
          setTimeout(function () {
            if (path === state.roomPhoto && !state.outlines.length) {
              fetchOutlines(true);
            }
          }, 60000);
        }
      });
  }

  function renderOutlines() {
    var layer = $("outlineLayer");
    if (!layer) return;
    layer.innerHTML = "";
    var img = $("canvasImg");
    if (!state.roomPhoto || !state.outlines.length || !img ||
        !img.naturalWidth || !img.clientWidth) return;
    // The canvas image uses object-fit:contain, so it may letterbox
    // inside its element box. Map room pixels onto the drawn rect.
    var rw = img.naturalWidth, rh = img.naturalHeight;
    var ew = img.clientWidth, eh = img.clientHeight;
    var scale = Math.min(ew / rw, eh / rh);
    var dw = rw * scale, dh = rh * scale;
    var ox = (ew - dw) / 2, oy = (eh - dh) / 2;
    function pct(x, base) { return (x / base * 100) + "%"; }
    // Largest first so the smallest tap region stays clickable.
    var ordered = state.outlines.slice().sort(function (a, b) {
      return boxArea(b) - boxArea(a);
    });
    ordered.forEach(function (o) {
      var fill = document.createElement("div");
      fill.className = "ol-fill" +
        (state.selectedTarget === o.id ? " sel" : "") +
        (state.assignments[o.id] ? " assigned" : "");
      var url = "url(/" + String(o.mask_url || "").replace(/^\/+/, "") +
        ")";
      fill.style.left = pct(ox, ew);
      fill.style.top = pct(oy, eh);
      fill.style.width = pct(dw, ew);
      fill.style.height = pct(dh, eh);
      fill.style.webkitMaskImage = url;
      fill.style.maskImage = url;
      fill.dataset.fill = o.id;
      layer.appendChild(fill);
      var list = (o.boxes && o.boxes.length) ? o.boxes :
        [o.box || [0, 0, rw, rh]];
      list.forEach(function (box) {
        var tap = document.createElement("button");
        tap.type = "button";
        tap.className = "ol-tap" +
          (state.selectedTarget === o.id ? " sel" : "");
        tap.style.left = pct(ox + box[0] * scale, ew);
        tap.style.top = pct(oy + box[1] * scale, eh);
        tap.style.width = pct(Math.max(4, (box[2] - box[0]) * scale), ew);
        tap.style.height = pct(Math.max(4, (box[3] - box[1]) * scale), eh);
        tap.setAttribute("aria-label", targetLabel(o.id));
        var tag = document.createElement("span");
        tag.textContent = targetLabel(o.id) +
          (state.assignments[o.id] ? " · " + state.assignments[o.id] : "");
        tap.appendChild(tag);
        (function (id) {
          tap.addEventListener("click", function () {
            selectTarget(id, true);
          });
          tap.addEventListener("mouseenter", function () {
            hoverFill(id, true);
          });
          tap.addEventListener("mouseleave", function () {
            hoverFill(id, false);
          });
        })(o.id);
        layer.appendChild(tap);
      });
    });
    renderItemPicker();
  }

  function hoverFill(id, on) {
    var fills = document.querySelectorAll('.ol-fill[data-fill="' +
                                          id + '"]');
    for (var i = 0; i < fills.length; i++) {
      fills[i].classList.toggle("hover", !!on);
    }
  }

  // Item picker: one square thumbnail per detected item, cropped from
  // the room photo around the item's box, plus "All". Tapping one is the
  // same selection as a chip or an outline tap.
  var ALL_WORDS = ["all", "الكل", "كل", "tout", "tous", "todo", "todos",
                   "सभी", "everything", "mix"];

  function pickerItems() {
    return (state.outlines || []).filter(function (o) {
      return o && o.id && (o.box || (o.boxes && o.boxes.length)) && o.size;
    }).slice().sort(function (a, b) { return boxArea(b) - boxArea(a); });
  }

  function pickerImage() {
    var path = state.roomPhoto;
    if (!path) return null;
    if (state.pickerImg && state.pickerImg.dataset.path === path) {
      return state.pickerImg;
    }
    var img = new Image();
    img.dataset.path = path;
    img.addEventListener("load", function () {
      if (state.roomPhoto === path) {
        state.pickerThumbs = {};
        renderItemPicker();
        refreshChatPicker();
      }
    });
    img.src = "/" + String(path).replace(/^\/+/, "");
    state.pickerImg = img;
    return img;
  }

  function pickerThumb(o) {
    var key = state.roomPhoto + "|" + o.id;
    state.pickerThumbs = state.pickerThumbs || {};
    if (state.pickerThumbs[key]) return state.pickerThumbs[key];
    var img = pickerImage();
    if (!img || !img.complete || !img.naturalWidth) return "";
    // Crop around the largest single region (a union box of two
    // pillows would show the whole sofa), falling back to the item box.
    var box = null;
    (o.boxes || []).forEach(function (bx) {
      if (bx && (!box || boxArea({ box: bx }) > boxArea({ box: box }))) {
        box = bx;
      }
    });
    box = box || o.box;
    if (!box) return "";
    var iw = img.naturalWidth, ih = img.naturalHeight;
    var sx = iw / ((o.size && o.size[0]) || iw);
    var sy = ih / ((o.size && o.size[1]) || ih);
    var bw = (box[2] - box[0]) * sx, bh = (box[3] - box[1]) * sy;
    var cx = (box[0] * sx) + bw / 2, cy = (box[1] * sy) + bh / 2;
    var side = Math.max(bw, bh) * 1.2;
    side = Math.max(24, Math.min(side, Math.min(iw, ih)));
    var x0 = Math.max(0, Math.min(iw - side, cx - side / 2));
    var y0 = Math.max(0, Math.min(ih - side, cy - side / 2));
    var out = "";
    try {
      var cv = document.createElement("canvas");
      cv.width = 160;
      cv.height = 160;
      var ctx = cv.getContext("2d");
      ctx.drawImage(img, x0, y0, side, side, 0, 0, 160, 160);
      out = cv.toDataURL("image/jpeg", 0.82);
    } catch (e) {
      out = "";
    }
    if (out) state.pickerThumbs[key] = out;
    return out;
  }

  function itemPickerHTML() {
    var items = pickerItems();
    if (!items.length) return "";
    var selected = state.selectedTarget;
    var html = items.map(function (o) {
      var src = pickerThumb(o);
      var code = state.assignments[o.id];
      return '<button type="button" class="item-thumb' +
        (selected === o.id ? " sel" : "") + '" data-outline="' +
        esc(o.id) + '" aria-label="' + esc(targetLabel(o.id)) +
        '" aria-pressed="' + (selected === o.id ? "true" : "false") +
        '"><span class="it-img">' +
        (src ? '<img src="' + src + '" alt="">' : "") + "</span>" +
        '<span class="it-l" dir="auto">' + esc(targetLabel(o.id)) +
        (code ? '<small>' + esc(code) + "</small>" : "") +
        "</span></button>";
    }).join("");
    if (items.length > 1) {
      html += '<button type="button" class="item-thumb all' +
        (selected === "all" ? " sel" : "") +
        '" data-outline="all" aria-label="' + esc(t("allItems")) +
        '"><span class="it-img it-all"><i data-lucide="layers" ' +
        'aria-hidden="true"></i></span><span class="it-l">' +
        esc(t("allItems")) + "</span></button>";
    }
    return '<div class="item-picker" role="group" aria-label="' +
      esc(t("tapToChange")) + '">' + html + "</div>";
  }

  function renderItemPicker() {
    var wrap = $("itemPicker");
    if (!wrap) return;
    var html = state.roomPhoto ? itemPickerHTML() : "";
    wrap.hidden = !html;
    wrap.innerHTML = html;
    if (html) icons();
  }

  function refreshChatPicker() {
    var slots = messagesEl ? messagesEl.querySelectorAll(
      ".outline-msg .picker-slot") : [];
    if (!slots.length) return;
    var html = itemPickerHTML();
    for (var i = 0; i < slots.length; i++) slots[i].innerHTML = html;
    if (html) icons();
  }

  function renderAssignRow() {
    var row = $("assignRow");
    if (!row) return;
    var chosen = state.chosenTargets || [];
    if (!state.roomPhoto || !chosen.length) {
      row.hidden = true;
      row.innerHTML = "";
      return;
    }
    row.hidden = false;
    var html = chosen.map(function (tg) {
      var code = state.assignments[tg];
      return '<button type="button" class="assign-chip' +
        (state.selectedTarget === tg ? " sel" : "") +
        '" data-target="' + esc(tg) + '">' + esc(targetLabel(tg)) +
        " · " + esc(code || t("pickOne")) + "</button>";
    }).join("");
    if (Object.keys(state.assignments).length) {
      html += '<button type="button" class="ghost-btn" id="applyAllBtn">' +
        esc(t("applyAll")) + " (" +
        Object.keys(state.assignments).length + ")</button>";
    }
    html += '<button type="button" class="ghost-btn" id="resetAssignBtn">' +
      esc(t("resetPicks")) + "</button>";
    row.innerHTML = html;
  }

  function resetAssignments() {
    fetchReq("/api/session/" + encodeURIComponent(state.sessionId) +
             "/assignments", { method: "DELETE", timeoutMs: 30000,
                               retries: 0 })
      .then(function (data) {
        state.assignments = (data && data.assignments) || {};
        state.selectedTarget = null;
        state.browseFor = null;
        renderAssignRow();
        renderOutlines();
        renderBrowse();
      }).catch(function () {});
  }

  function openBrowse(target) {
    var tg = target || state.selectedTarget ||
      (state.chosenTargets || [])[0];
    if (!tg) return;
    state.selectedTarget = tg;
    state.browseFor = tg;
    renderAssignRow();
    renderOutlines();
    var panel = $("browsePanel");
    if (!panel) return;
    panel.hidden = false;
    panel.innerHTML = '<div class="browse-head"><b>' +
      esc(t("browseTitle")) + " · " + esc(targetLabel(tg)) +
      '</b><button type="button" class="ghost-btn" id="browseClose">' +
      esc(t("closeBrowse")) + "</button></div>" +
      '<div class="browse-grid"><span class="typing"><span></span>' +
      "<span></span><span></span></span></div>";
    $("browseClose").addEventListener("click", function () {
      panel.hidden = true;
      state.browseFor = null;
    });
    fetchReq("/api/fabrics?suitable_for=" + encodeURIComponent(tg) +
             "&limit=12", { method: "GET", timeoutMs: 60000, retries: 1 })
      .then(function (data) {
        if (state.browseFor !== tg) return;
        state.browseList = (data && data.fabrics) || [];
        renderBrowseItems();
      }).catch(function () {
        if (state.browseFor !== tg) return;
        panel.querySelector(".browse-grid").textContent = t("sendFail");
      });
  }

  function renderBrowse() {
    var panel = $("browsePanel");
    if (!panel || panel.hidden) return;
    if (state.browseFor) openBrowse(state.browseFor);
  }

  function renderBrowseItems() {
    var panel = $("browsePanel");
    if (!panel) return;
    var grid = panel.querySelector(".browse-grid");
    if (!grid) return;
    grid.innerHTML = state.browseList.map(function (f) {
      var name = state.lang === "ar" ? f.name_ar : f.name_en;
      return '<div class="browse-card"><img src="/' +
        esc((f.image || "").replace(/^\/+/, "")) + '" alt="' +
        esc(name) + '" loading="lazy">' +
        '<div class="browse-n" dir="auto">' + esc(name) + "</div>" +
        '<div class="browse-m">' + esc(f.code) + " · " +
        esc(formatPrice(f.price_sar_per_m)) + "</div>" +
        '<button type="button" class="seeit" data-apply="' +
        esc(f.code) + '"><span>' + esc(t("applyOne")) +
        "</span></button></div>";
    }).join("");
  }

  function applyBrowse(code) {
    var tg = state.browseFor || state.selectedTarget ||
      (state.chosenTargets || [])[0];
    if (!tg) return;
    postJSON("/api/session/" + encodeURIComponent(state.sessionId) +
             "/assignments", { target: tg, code: code }, 30000, 1)
      .then(function (data) {
        state.assignments = (data && data.assignments) || {};
        state.assignments[tg] = code;
        renderAssignRow();
        renderOutlines();
      }).catch(function () {});
    tryFabric(code, tg);
  }

  function showSwapStep(label, model) {
    var scope = pendingScope();
    var el = scope && scope.querySelector(".agent-step");
    if (!el) return;
    el.innerHTML = esc(canvasStepLabel(label)) + modelBadge(model);
    el.classList.remove("swap");
    void el.offsetWidth;
    el.classList.add("swap");
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  var MULTI_DEADLINE_MS = 115000;

  function runMultiSwap() {
    var list = Object.keys(state.assignments).map(function (k) {
      return { target: k, code: state.assignments[k] };
    });
    if (!list.length || state.multiRunning || !state.roomPhoto) return;
    state.multiRunning = true;
    pendingBubble();
    showSwapStep("segment");
    var reader = null, settled = false, gotDone = false;
    var ctrl = null, watchdog = null;
    function multiFail(timedOut) {
      if (settled) return;
      settled = true;
      if (watchdog) clearTimeout(watchdog);
      state.multiRunning = false;
      try { if (reader) reader.cancel(); } catch (e) {}
      try { if (ctrl) ctrl.abort(); } catch (e) {}
      dropPending();
      addMsg(timedOut ? t("swapTimeout") : t("swapFail"), "them");
    }
    function multiDone(result) {
      if (settled) return;
      settled = true;
      gotDone = true;
      if (watchdog) clearTimeout(watchdog);
      try { if (reader) reader.cancel(); } catch (e) {}
      finalizeMulti(result || {});
    }
    try {
      if (typeof AbortController !== "undefined") {
        ctrl = new AbortController();
        watchdog = setTimeout(function () { multiFail(true); },
                              MULTI_DEADLINE_MS);
      }
      var init = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId,
                               image_path: state.roomPhoto,
                               assignments: list })
      };
      if (ctrl) init.signal = ctrl.signal;
      fetch("/api/swap/multi/stream", init).then(function (r) {
        if (settled) return;
        if (!r.ok || !r.body) throw new Error("HTTP " + r.status);
        reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function onEvt(evt) {
          if (settled) return;
          if (evt.type === "step") {
            showSwapStep(evt.label, evt.model);
          } else if (evt.type === "done") {
            multiDone(evt.result);
          } else if (evt.type === "error") {
            multiFail(!!evt.timeout);
          }
        }
        function pump() {
          return reader.read().then(function (step) {
            if (settled) return;
            // EOF without done means the proxy cut the stream: fail
            // instead of spinning forever with multiRunning stuck.
            if (step.done) { multiFail(true); return; }
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
      }).catch(function () {
        if (!gotDone) multiFail(false);
      });
    } catch (e) {
      multiFail(false);
    }
  }

  function metaFor(code) {
    var lists = [state.lastRecs || [], state.browseList || []];
    for (var i = 0; i < lists.length; i++) {
      for (var j = 0; j < lists[i].length; j++) {
        var f = lists[i][j];
        if (f.code === code) {
          return Promise.resolve({ code: f.code, name_en: f.name_en,
                                   name_ar: f.name_ar,
                                   price: f.price_sar_per_m,
                                   image: f.image });
        }
      }
    }
    return fetchReq("/api/fabric/" + encodeURIComponent(code),
                    { method: "GET", timeoutMs: 30000, retries: 1 })
      .then(function (f) {
        return { code: f.code, name_en: f.name_en, name_ar: f.name_ar,
                 price: f.price_sar_per_m, image: f.image };
      }).catch(function () { return { code: code }; });
  }

  function fmtMeters(n) {
    if (n === undefined || n === null) return "";
    if (state.lang === "ar") return toArabicDigits(n) + " " + t("meterUnit");
    return n + " " + t("meterUnit");
  }

  function fmtMoney(n) {
    if (n === undefined || n === null) return "";
    if (state.lang === "ar") return toArabicDigits(n) + " " + t("sarUnit");
    return n + " " + t("sarUnit");
  }

  function fmtNum(n) {
    if (n === undefined || n === null) return "";
    if (state.lang === "ar") return toArabicDigits(n);
    return String(n);
  }

  function waSummaryText(rows, total, co2line, link) {
    var lines = rows.map(function (r) {
      return "• " + r.target + " → " + r.name + " (" + r.code + "): " +
        (r.meters !== undefined && r.meters !== null ?
          fmtMeters(r.meters) + " × " + fmtMoney(r.price) + " = " +
            fmtMoney(r.line) :
          t("needsMeasure"));
    });
    lines.push(t("totalLabel") + ": " + total);
    lines.push(t("preliminaryNote"));
    if (co2line) lines.push(co2line);
    // The preview travels as a public 14-day share link (the site
    // itself stays locked, so a raw uploads path would 401).
    if (link) lines.push(link);
    return lines.join("\n");
  }

  function fetchQuote() {
    return fetchReq("/api/session/" +
                     encodeURIComponent(state.sessionId) + "/quote",
                     { method: "GET", timeoutMs: 30000, retries: 1 })
      .catch(function () { return null; });
  }

  function postSummaryCard(results, skipped, quotePre) {
    // results: applied swap items (Apply-all). Without them the card is
    // built from the session quote alone: every quoted item, with its
    // swap thumbnail when one exists (any quote, single item too).
    skipped = skipped || [];
    if (!results) {
      return fetchQuote().then(function (quote) {
        var items = (quote && quote.items) || [];
        if (!items.length) return null;
        var rows = items.map(function (it) {
          var done = state.swaps[it.code] || {};
          return { target: it.target, code: it.code,
                   result_url: done.result_url || "",
                   scores: done.scores || null };
        });
        return postSummaryCard(rows, [], quote);
      });
    }
    return Promise.all(results.map(function (r) {
      return metaFor(r.code);
    })).then(function (metas) {
      return (quotePre ? Promise.resolve(quotePre) : fetchQuote())
        .then(function (quote) {
          var byTarget = {};
          (quote && quote.items || []).forEach(function (it) {
            byTarget[it.target] = it;
          });
          var waRows = [];
          var rows = results.map(function (r, i) {
            var meta = metas[i] || { code: r.code };
            var name = state.lang === "ar" ? (meta.name_ar || meta.code)
                                           : (meta.name_en || meta.code);
            var q = byTarget[r.target] || {};
            var bits = esc(r.code) +
              (meta.price !== undefined ?
                " · " + esc(formatPrice(meta.price)) : "");
            if (q.meters !== undefined && q.meters !== null) {
              bits += " · " + esc(fmtMeters(q.meters));
              if (q.line_total !== undefined && q.line_total !== null) {
                bits += " · " + esc(fmtMoney(q.line_total));
              }
            } else if (quote) {
              bits += " · " + esc(t("needsMeasure"));
            }
            waRows.push({ target: targetLabel(r.target), name: name,
                          code: r.code,
                          meters: q.meters, price: meta.price,
                          line: q.line_total });
            var sc = r.scores || null;
            var scoreHtml = "";
            if (sc) {
              var itemMatch = Math.min.apply(null, [
                sc.color, sc.pattern, sc.scale, sc.isolation
              ].map(function (v) { return v || 0; }));
              scoreHtml = '<span class="match-badge small">' +
                esc(matchBadgeText(itemMatch)) + "</span>";
            }
            var thumb = r.result_url ?
              '<img class="swap-thumb" src="/' +
                esc((r.result_url || "").replace(/^\/+/, "")) + '" alt="' +
                esc(name) + '" data-code="' + esc(r.code) + '">' :
              (meta.image ? '<img class="swap-thumb sum-swatch" src="/' +
                esc(meta.image) + '" alt="' + esc(name) + '">' : "");
            return '<div class="sum-row">' + thumb +
              "<div><div><b>" + esc(targetLabel(r.target)) + "</b> → " +
              esc(name) + " " + scoreHtml + "</div><div>" + bits +
              "</div></div></div>";
          }).join("");
          var skipHtml = skipped.map(function (s) {
            var what = targetLabel(s.target) + (s.code ? " · " + s.code : "");
            var why = s.reason ? " (" + reasonLabel(s.reason) + ")" : "";
            return '<div class="sum-skip" dir="auto"><span>' +
              esc(t("notApplied").replace("%s", what) + why) + "</span>" +
              (s.code ? '<button type="button" class="ghost-btn sum-retry" ' +
                'data-try="' + esc(s.code) + '" data-target="' +
                esc(s.target) + '">' + esc(t("tryAgain")) + "</button>" : "") +
              "</div>";
          }).join("");
          var extra = "";
          var co2txt = "";
          var hasQuote = !!(quote && quote.items && quote.items.length);
          if (hasQuote) {
            extra = '<div class="sum-total"><b>' + esc(t("totalLabel")) +
              "</b> " + esc(fmtMoney(quote.total)) + "</div>" +
              '<p class="coming">' + esc(t("preliminaryNote")) + "</p>";
            if (quote.co2 && quote.co2.kg > 0) {
              var pieces = results.map(function (r) {
                return targetLabel(r.target);
              }).join(" + ");
              co2txt = t("co2Line").replace("%s", pieces)
                .replace("%d", fmtNum(quote.co2.kg))
                .replace("%d", fmtNum(quote.co2.waste_kg));
              extra += '<div class="co2-line"><i data-lucide="leaf" ' +
                'aria-hidden="true"></i><div>' + esc(co2txt) +
                ' <span class="co2-src">' + esc(t("co2Source")) +
                "</span></div></div>" +
                '<p class="coming">' + esc(t("co2Note")) + "</p>";
            }
          }
          var linkP = Promise.resolve("");
          var shareFrom = state.canvasView ||
            (results.length && results[0].result_url ?
              "/" + String(results[0].result_url).replace(/^\/+/, "") : "");
          if (hasQuote && shareFrom) {
            linkP = fetchReq("/api/share", {
                method: "POST",
                json: { result_url: shareFrom },
                timeoutMs: 30000, retries: 1 })
              .then(function (shareRes) {
                if (shareRes && shareRes.share_path) {
                  var origin = "";
                  try { origin = window.location.origin; }
                  catch (e) {}
                  return origin + shareRes.share_path;
                }
                return "";
              })
              .catch(function () { return ""; });
          }
          return linkP.then(function (shareLink) {
            var waText = hasQuote ? waSummaryText(
              waRows, fmtMoney(quote.total), co2txt, shareLink) : "";
            var div = document.createElement("div");
            div.className = "msg them";
            div.innerHTML = AVATAR +
              '<div dir="auto"><div class="sum-card">' +
              "<b>" + esc(t("summaryTitle")) + "</b>" + rows +
              skipHtml + extra +
              (waText ?
                '<div class="sum-actions"><a class="seeit" ' +
                'target="_blank" rel="noopener" ' +
                'href="https://wa.me/?text=' +
                encodeURIComponent(waText) + '"><span>' +
                esc(t("sendUpholsterer")) + "</span></a>" +
                '<button type="button" class="ghost-btn sum-copy">' +
                "<span>" + esc(t("copySummary")) +
                "</span></button></div>" : "") +
              "</div></div>";
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
            var copyBtn = div.querySelector(".sum-copy");
            if (copyBtn) {
              copyBtn.addEventListener("click", function () {
                var done = function () {
                  copyBtn.querySelector("span").textContent =
                    t("copiedTick");
                };
                if (navigator.clipboard &&
                    navigator.clipboard.writeText) {
                  navigator.clipboard.writeText(waText).then(done, done);
                } else {
                  var ta = document.createElement("textarea");
                  ta.value = waText;
                  document.body.appendChild(ta);
                  try { ta.select(); document.execCommand("copy"); }
                  catch (e) {}
                  document.body.removeChild(ta);
                  done();
                }
              });
            }
            icons();
          });
        });
    });
  }

  function finalizeMulti(res) {
    state.multiRunning = false;
    dropPending();
    var results = (res && res.results) || [];
    if (!results.length) {
      addMsg(t("swapFail"), "them");
      return;
    }
    var before = state.roomPhoto || "";
    (res.skipped || []).forEach(function (sk) {
      // Not applied: never shown as a pick, never counted in the quote.
      if (sk && sk.target) delete state.assignments[sk.target];
    });
    renderAssignRow();
    results.forEach(function (r) {
      var entry = { fabric_code: r.code, result_url: r.result_url,
                    mask_url: r.mask_url, before_url: before,
                    scores: r.scores || {}, attempts: r.attempts || 1,
                    checks: r.checks || null, target: r.target || "",
                    created_at: Date.now() / 1000, meta: null };
      before = r.result_url || before;
      state.prevList.push(entry);
      state.swaps[r.code] = entry;
    });
    state.canvasView = "/" + String(
      (res.final_url || results[results.length - 1].result_url || "")
      ).replace(/^\/+/, "");
    renderStrip();
    renderCanvas();
    metaFor(results[results.length - 1].code).then(function (meta) {
      var last = state.swaps[results[results.length - 1].code];
      if (last) last.meta = meta;
      renderStrip();
    });
    postSummaryCard(results, res.skipped || []).then(function () {
      var last = state.swaps[results[results.length - 1].code];
      if (last) {
        if (!last.meta) {
          last.meta = { code: last.fabric_code };
        }
        postSwapMessage(last);
      }
    });
  }

  function loadSample(id) {
    if (["living", "curtains", "majlis", "armchair"].indexOf(id) < 0) {
      return;
    }
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
    // Desktop recommendations live under the photo (renderCanvasRow);
    // the old chat-pane card panel stays empty and hidden.
    if (!recsEl) return;
    recsEl.innerHTML = "";
    recsEl.hidden = true;
  }

  function tryOnLabel(target) {
    var words = t("tryWord") || {};
    var word = words[target] || targetLabel(target);
    return (t("tryOnTarget") || "Try on the %s").replace("%s", word);
  }

  function receiptLine(r) {
    if (!r.receipt) return "";
    return '<p class="receipt-line" dir="auto">' + esc(r.receipt) + "</p>";
  }

  function miniRecsHTML(recs) {
    return '<div class="mini-recs">' + recs.map(function (r) {
      var name = state.lang === "ar" ? r.name_ar : r.name_en;
      var tgt = r.target || state.selectedTarget || "";
      var label = tgt && SWAP_TARGETS.indexOf(tgt) >= 0 ?
        tryOnLabel(tgt) : t("tryOn");
      return '<div class="mini-card" data-fabric="' + esc(r.code) +
        '" role="button" tabindex="0">' +
        '<img src="/' + esc(r.image) + '" alt="' + esc(name) +
        '" loading="lazy">' +
        '<div class="mini-n" dir="auto">' + esc(name) + "</div>" +
        '<div class="mini-m">' + esc(r.code) + " · " +
        esc(formatPrice(r.price_sar_per_m)) + "</div>" +
        receiptLine(r) +
        '<button type="button" class="seeit mini-try" data-try="' +
        esc(r.code) + '"' + (tgt ? ' data-target="' + esc(tgt) + '"' : "") +
        '><span>' + esc(label) + "</span></button>" +
        "</div>";
    }).join("") + "</div>";
  }

  function fewQualifyNote(recs) {
    if (!recs || recs.length >= 3) return "";
    return '<p class="few-qualify" dir="auto">' +
      esc((t("fewQualify") || "Only %d fabrics qualified.").replace(
        "%d", String(recs.length))) + "</p>";
  }

  function appendRecsToChat(recs) {
    var div = document.createElement("div");
    div.className = "msg them recs-msg";
    div.innerHTML = AVATAR + '<div class="recs-body" dir="auto">' +
      fewQualifyNote(recs) + miniRecsHTML(recs) + "</div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    icons();
    return div;
  }

  function appendRecsLine() {
    var div = document.createElement("div");
    div.className = "msg them recs-line";
    div.innerHTML = AVATAR + '<div><p class="ptext" dir="auto">' +
      esc(t("recsUnderPhoto")) + "</p></div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function showRecs(recs) {
    if (!recs || !recs.length) return;
    if (isNarrow()) {
      appendRecsToChat(recs);
    } else {
      renderCanvasRow();
      appendRecsLine();
    }
  }

  function maybeAutoPreview(res) {
    if (res && res.preview && res.preview.code) {
      // Mark this turn's reply bubble: when the swap lands, its text
      // folds into the single swap message instead of a second bubble.
      var bubbles = messagesEl.querySelectorAll(".msg.them");
      for (var i = bubbles.length - 1; i >= 0; i--) {
        if (bubbles[i].querySelector(".ptext")) {
          bubbles[i].setAttribute("data-auto", "1");
          break;
        }
      }
      var opts = { keepMark: true };
      if (res.preview.target) opts.target = res.preview.target;
      tryFabric(res.preview.code, opts.target, { keepMark: true });
    }
  }

  function handleResult(res) {
    autoLang(res);
    if (res.targets) {
      state.assignments = res.targets.assignments || {};
      state.chosenTargets = res.targets.chosen || [];
      if (state.chosenTargets.length === 1 &&
          SWAP_TARGETS.indexOf(state.chosenTargets[0]) >= 0) {
        state.selectedTarget = state.chosenTargets[0];
      }
    }
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
    postOutlineMessage();
    if (res.recommendations && res.recommendations.length) {
      showRecs(res.recommendations);
    }
    if (!afterQuote(res)) renderOptions(state.lastOptions);
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

  var MODEL_BADGE = { "muse-spark-1.3": "Spark",
                      "muse-image-1.0": "Image", "sam-3.1": "SAM" };

  function modelBadge(model) {
    var short = MODEL_BADGE[model];
    if (!short) return "";
    return ' <span class="model-badge">' + esc(short) + "</span>";
  }

  var SWAP_STAGE_MODEL = ["sam-3.1", "muse-image-1.0", "muse-spark-1.3"];

  function paintStepBadges() {
    var items = document.querySelectorAll("#swapSteps li");
    var labels = [t("stepDetect"), t("stepApply"), t("stepCheck")];
    for (var i = 0; i < 3 && i < items.length; i++) {
      if (items[i].id === "swapRetryRow") continue;
      items[i].innerHTML = esc(labels[i]) +
        modelBadge(SWAP_STAGE_MODEL[i]);
    }
  }

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

  function tryFabric(code, target, opts) {
    opts = opts || {};
    if (target && SWAP_TARGETS.indexOf(target) < 0) target = "";
    var resolvedTarget = target ||
      (SWAP_TARGETS.indexOf(opts.target) >= 0 ? opts.target : "");
    // Same fabric already rendering (auto-preview + manual tap racing,
    // double-click, script retry): ride the in-flight swap instead of
    // burning a second model run and posting a twin bubble. A different
    // explicit target still counts as a new swap.
    if (state.pendingSwap && state.pendingSwap === code &&
        (!resolvedTarget || resolvedTarget === state.swapTarget)) {
      if ($("swapModal").hidden) {
        $("swapModal").hidden = false;
        document.body.classList.add("modal-open");
      }
      return;
    }
    if (resolvedTarget) state.selectedTarget = resolvedTarget;
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
    // New swap supersedes any in-flight one: bump the sequence token
    // and abort the previous fetch so stale events cannot corrupt this
    // modal (A's result drawn into B's modal, A's failure closing B).
    state.swapSeq = (state.swapSeq || 0) + 1;
    var seq = state.swapSeq;
    if (state.swapController) {
      try { state.swapController.abort(); } catch (e) {}
      state.swapController = null;
    }
    var openOpts = { target: resolvedTarget || undefined,
                     keepMark: opts.keepMark,
                     noRetry: opts.noRetry,
                     review: opts.review,
                     _seq: seq };
    openSwap(code, openOpts);
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
    // One short receipt line only (see receipt_summary server-side).
    var receipts = receiptLine(r);
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
    if (r.target) btn.setAttribute("data-target", r.target);
    else btn.removeAttribute("data-target");
    btn.querySelector("span").textContent =
      (r.target && SWAP_TARGETS.indexOf(r.target) >= 0) ?
      tryOnLabel(r.target) : t("tryOn");
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
    // All entry points must ride the sequence token in tryFabric so a
    // previous swap is aborted and stale events are ignored.
    if (!opts._seq && !opts.review) {
      tryFabric(code, opts.target, opts);
      return;
    }
    var seq = opts._seq || state.swapSeq;
    // A new manual swap supersedes any earlier auto-preview mark.
    if (!opts.keepMark) {
      var stale = messagesEl.querySelectorAll('[data-auto="1"]');
      for (var si = 0; si < stale.length; si++) {
        stale[si].removeAttribute("data-auto");
      }
    }
    closeFabricSheet();
    if (!state.roomPhoto && !opts.review) {
      tryFabric(code);
      return;
    }
    state.swapCode = code;
    state.swapRetried = !!opts.noRetry;
    // The chosen item wins: explicit call arg, then the user's current
    // selection (chip/outline tap or recommendation card), then the
    // detected-piece guess. Never silently swap a different item.
    var target = SWAP_TARGETS.indexOf(opts.target) >= 0 ? opts.target :
      (SWAP_TARGETS.indexOf(state.selectedTarget) >= 0 ?
        state.selectedTarget : swapTarget());
    if (!opts.target && state.selectedTarget === "all" &&
        (state.chosenTargets || []).length === 1 &&
        SWAP_TARGETS.indexOf(state.chosenTargets[0]) >= 0) {
      target = state.chosenTargets[0];
    }
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
    state.swapTarget = target;
    state.pendingSwapLabel = t("stepDetect");
    $("swapSteps").hidden = false;
    $("swapTimeoutMsg").hidden = true;
    $("swapRetryBtn").hidden = true;
    if ($("swapTrace")) $("swapTrace").hidden = true;
    if ($("hoodToggle")) $("hoodToggle").hidden = true;
    state.pendingSwapModel = null;
    state.swapTrace = [];
    state.swapTraceEnd = null;
    paintStepBadges();
    renderCanvasRow();
    clearSwapTimers();
    swapTimers.push(setTimeout(function () {
      if (!$("swapModal").hidden) $("swapStill").hidden = false;
    }, 60000));
    state.swapAttemptT0 = Date.now();
    startSwapAttempt(code, target, swapFabricMeta(code), 0, seq);
  }

  var SWAP_DEADLINE_MS = 115000;

  function reasonLabel(reason) {
    if (reason === "colour mismatch") return t("checkColour");
    if (reason === "low coverage") return t("checkCoverage");
    return reason || "";
  }

  function showSwapTimeout(message) {
    clearSwapTimers();
    state.pendingSwap = null;
    state.pendingSwapLabel = null;
    renderCanvasRow();
    $("swapSteps").hidden = true;
    $("swapStill").hidden = true;
    var m = $("swapTimeoutMsg");
    m.textContent = message || t("swapTimeout");
    m.hidden = false;
    var b = $("swapRetryBtn");
    b.textContent = t("tryAgain");
    b.hidden = false;
  }

  function startSwapAttempt(code, target, meta, attempt, seq) {
    var mySeq = seq || state.swapSeq;
    function isStale() { return mySeq !== state.swapSeq; }
    var remaining = SWAP_DEADLINE_MS -
      (Date.now() - (state.swapAttemptT0 || Date.now()));
    if (remaining <= 0) {
      if (!isStale()) showSwapTimeout();
      return;
    }
    var ctrl = null, watchdog = null, reader = null, settled = false;
    if (typeof AbortController !== "undefined") {
      ctrl = new AbortController();
      state.swapController = ctrl;
      watchdog = setTimeout(function () {
        if (isStale()) return;
        try { ctrl.abort(); } catch (e) {}
        onAttemptFailed(true);
      }, remaining);
    }
    function stopWatch() {
      if (watchdog) clearTimeout(watchdog);
    }
    function releaseCtrl() {
      if (state.swapController === ctrl) state.swapController = null;
    }
    function onAttemptFailed(timedOut) {
      if (settled || isStale()) return;
      settled = true;
      stopWatch();
      releaseCtrl();
      try { if (reader) reader.cancel(); } catch (e) {}
      if (timedOut && attempt < 1) {
        startSwapAttempt(code, target, meta, attempt + 1, mySeq);
        return;
      }
      if (timedOut) {
        showSwapTimeout();
        return;
      }
      state.pendingSwap = null;
      state.pendingSwapLabel = null;
      renderCanvasRow();
      hideSwapModal();
      addMsg(t("swapFail"), "them");
    }
    function onEvt(evt) {
      if (isStale()) return;
      if (evt.type === "step") {
        $("swapTryAgain").hidden = true;
        $("swapRetryBtn").hidden = true;
        state.pendingSwapLabel = canvasStepLabel(evt.label);
        state.pendingSwapModel = evt.model || null;
        (state.swapTrace = state.swapTrace || []).push(
          { label: evt.label, model: evt.model || null,
            t: Date.now() });
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
        if (settled || isStale()) return;
        settled = true;
        state.swapTraceEnd = Date.now();
        stopWatch();
        releaseCtrl();
        try { if (reader) reader.cancel(); } catch (e) {}
        finalizeSwap(code, meta, evt.result || {});
      } else if (evt.type === "error" && evt.reason && !evt.timeout) {
        if (settled || isStale()) return;
        settled = true;
        stopWatch();
        releaseCtrl();
        try { if (reader) reader.cancel(); } catch (e) {}
        var what = targetLabel(evt.target || target) + " · " + code;
        showSwapTimeout(t("notApplied").replace("%s", what) + " (" +
                        reasonLabel(evt.reason) + ")");
        addMsg(t("notApplied").replace("%s", what) + " (" +
               reasonLabel(evt.reason) + ")", "them");
      } else if (evt.type === "error") {
        onAttemptFailed(!!evt.timeout);
      }
    }
    var buf = "";
    var dec = new TextDecoder();
    function pump() {
      return reader.read().then(function (step) {
        if (settled || isStale()) return;
        if (step.done) {
          onAttemptFailed(true);
          return;
        }
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
    try {
      var init = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId,
                               image_path: state.roomPhoto,
                               fabric_code: code, target: target })
      };
      if (ctrl) init.signal = ctrl.signal;
      fetch("/api/swap/stream", init).then(function (r) {
        if (settled || isStale()) return;
        if (!r.ok || !r.body) { onAttemptFailed(true); return; }
        reader = r.body.getReader();
        return pump();
      }).catch(function () {
        if (!isStale()) onAttemptFailed(true);
      });
    } catch (e) {
      onAttemptFailed(true);
    }
  }

  function renderTrace(res) {
    var box = $("swapTrace");
    if (!box) return;
    // Each row shows how long ITS step ran: until the next step began,
    // or until the result arrived for the last one.
    var trace = state.swapTrace || [], html = "";
    var end = state.swapTraceEnd || Date.now();
    trace.forEach(function (s, i) {
      var next = i + 1 < trace.length ? trace[i + 1].t : end;
      var secs = Math.max(0, (next - s.t) / 1000);
      html += '<div class="trace-row"><span dir="auto">' +
        esc(canvasStepLabel(s.label)) + "</span>" +
        modelBadge(s.model) +
        '<span class="trace-secs">' + secs.toFixed(1) + "s</span></div>";
    });
    var checks = (res && res.checks) || null;
    if (checks && checks.delta_e !== undefined && checks.delta_e !== null) {
      html += '<div class="trace-row"><span dir="auto">' +
        esc(t("traceChecks").replace("%s", String(checks.delta_e))
          .replace("%s", Math.round((checks.coverage || 0) * 100) + "%")) +
        "</span><span class=\"trace-secs\">" +
        (checks.ok ? "✓" : "✗") + "</span></div>";
    }
    var scores = (res && res.scores) || {};
    html += '<div class="trace-row total"><span>match ' +
      [scores.color, scores.pattern, scores.scale, scores.isolation]
        .map(function (v) { return v || 0; }).join(" · ") +
      " · tries " + ((res && res.attempts) || 1) + "</span></div>";
    box.innerHTML = html;
    box.hidden = true;
    var btn = $("hoodToggle");
    if (btn) { btn.textContent = t("underHood"); btn.hidden = false; }
  }

  function finalizeSwap(code, meta, res) {
    // Server fabric meta fills gaps when the swap was triggered outside
    // the recommendation list (browse panel, multi-apply): without it the
    // result bubble shows the code twice and no price.
    var srv = (res && res.fabric) || {};
    meta = meta || { code: code };
    if (!meta.name_en && srv.name_en) meta.name_en = srv.name_en;
    if (!meta.name_ar && srv.name_ar) meta.name_ar = srv.name_ar;
    if (meta.price === undefined && srv.price_sar_per_m !== undefined) {
      meta.price = srv.price_sar_per_m;
    }
    if (!meta.image && srv.image) meta.image = srv.image;
    clearSwapTimers();
    var scores = res.scores || {};
    var vals = [scores.color, scores.pattern, scores.scale,
                scores.isolation].map(function (v) { return v || 0; });
    var match = Math.min.apply(null, vals);
    var before = state.roomPhoto ?
      "/" + state.roomPhoto.replace(/^\/+/, "") : "";
    var after = "/" + (res.result_url || "").replace(/^\/+/, "");
    renderSwapResult(before, after, res, match, vals, meta);
    renderTrace(res);
    var entry = { fabric_code: code,
                  result_url: res.result_url || "",
                  mask_url: res.mask_url || "",
                  before_url: state.roomPhoto || "",
                  scores: scores, attempts: res.attempts || 1,
                  checks: res.checks || null,
                  target: res.target || state.swapTarget || "",
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
    badge.textContent = matchBadgeText(match);
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
    // One bubble per fabric: a second result for the same code refreshes
    // the existing bubble instead of posting a twin (Try, then Apply the
    // same fabric from Browse, double taps). History stays available in
    // the previews strip; an exact re-post is still a no-op.
    var rel = String(entry.result_url || "").replace(/^\/+/, "");
    var thumbs = messagesEl.querySelectorAll(".chat-swap .swap-thumb");
    var existing = null;
    for (var ti = 0; ti < thumbs.length; ti++) {
      if (String(thumbs[ti].getAttribute("src") || "")
          .replace(/^\/+/, "") === rel && rel) return;
      if (!existing && thumbs[ti].getAttribute("data-code") ===
          entry.fabric_code) {
        existing = thumbs[ti].closest(".msg");
      }
    }
    var meta = entry.meta || { code: entry.fabric_code };
    var name = state.lang === "ar" ? (meta.name_ar || meta.code || "")
                                   : (meta.name_en || meta.code || "");
    var scores = entry.scores || {};
    var vals = [scores.color, scores.pattern, scores.scale,
                scores.isolation].map(function (v) { return v || 0; });
    var match = Math.min.apply(null, vals);
    // Fold the auto-preview turn's reply text into this message so the
    // swap never produces a second bubble.
    var followHtml = "";
    var marked = messagesEl.querySelectorAll('.msg.them[data-auto="1"]');
    if (marked.length) {
      var last = marked[marked.length - 1];
      var ptext = last.querySelector(".ptext");
      // ptext holds formatReply output (escaped text + <strong>/<br>),
      // so transplanting its HTML is safe.
      if (ptext && (ptext.textContent || "").trim()) {
        followHtml = ptext.innerHTML;
      }
      last.parentNode.removeChild(last);
    }
    var fabricImg = meta.image ?
      '<img class="chat-swap-fabric" src="/' + esc(meta.image) + '" alt="">' : "";
    var html = AVATAR + '<div dir="auto"><div class="chat-swap">' +
      '<img class="swap-thumb" src="/' +
      esc((entry.result_url || "").replace(/^\/+/, "")) + '" alt="' +
      esc(name) + '" data-code="' + esc(entry.fabric_code) + '">' +
      '<div class="chat-swap-row">' + fabricImg +
      "<div><div><b>" + esc(name) + "</b>" +
      (entry.target ? ' <span class="chat-swap-target">' +
        esc(targetLabel(entry.target)) + "</span>" : "") +
      "</div><div>" + esc(entry.fabric_code) +
      (meta.price !== undefined ? " · " + esc(formatPrice(meta.price)) : "") +
      "</div></div>" +
      '<span class="match-badge small">' +
      esc(matchBadgeText(match)) + "</span></div>" +
      (followHtml ? '<div class="chat-follow">' + followHtml + "</div>"
                  : '<p class="chat-follow">' + esc(t("followSwap")) +
                    "</p>") +
      "</div></div>";
    if (existing) {
      existing.innerHTML = html;
    } else {
      var div = document.createElement("div");
      div.className = "msg them";
      div.innerHTML = html;
      messagesEl.appendChild(div);
    }
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
      var gotToken = false, streamStarted = false;
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
        streamStarted = true;
        armStall();
        var reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function onEvt(evt) {
          if (evt.type === "step") {
            showStep(evt.label, evt.model);
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
        // A5: once the server accepted the stream it is still running
        // the turn; a second POST would run it again on the same session.
        if (gotToken || streamStarted || settled) { finish(e); return; }
        postJSON("/api/chat", {
          session_id: state.sessionId,
          message: text || "",
          image_path: imagePath || null,
          lang: state.pinned ? state.lang : null
        }, 120000, 0).then(function (res) {
          res.fallback = true;
          finish(null, res);
        }).catch(finish);
      });
    });
  }

  function setChatBusy(on) {
    // A2: one turn in flight at a time; chips/outlines/composer wait.
    state.chatBusy = !!on;
    document.body.classList.toggle("chat-busy", !!on);
    var btn = document.querySelector("#composer button[type=submit]");
    if (btn) btn.disabled = !!on;
  }

  function send(text, imagePath, photoPreview, silent) {
    if (!text && !imagePath) return;
    if (state.chatBusy) return;
    setChatBusy(true);
    if (!silent) addMsg(text || "", "me", photoPreview);
    // Old option chips belong to the turn that produced them.
    if (chipsEl) { chipsEl.innerHTML = ""; chipsEl.hidden = true; }
    // So does any auto-preview mark: a new user turn starts fresh.
    var stale = messagesEl.querySelectorAll('[data-auto="1"]');
    for (var si = 0; si < stale.length; si++) {
      stale[si].removeAttribute("data-auto");
    }
    pendingBubble();
    var thinkingTimer = setTimeout(function () {
      var scope = pendingScope();
      var body = scope && scope.querySelector(".ptext");
      if (body && !body.textContent) showStep("thinking");
    }, 8000);
    function finish() {
      clearTimeout(thinkingTimer);
      setChatBusy(false);
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
    if (res.targets) {
      state.assignments = res.targets.assignments || {};
      state.chosenTargets = res.targets.chosen || [];
      // The server's chosen item is the source of truth; a tap that
      // produced this turn already set selectedTarget to the same item.
      if (state.chosenTargets.length === 1 &&
          SWAP_TARGETS.indexOf(state.chosenTargets[0]) >= 0) {
        state.selectedTarget = state.chosenTargets[0];
      }
    }
    if (res.detected_piece) state.detectedPiece = res.detected_piece;
    if (res.recommendations && res.recommendations.length) {
      state.lastRecs = res.recommendations;
    }
    state.lastOptions = res.options || [];
    if (res.room_analysis) state.lastRoom = res.room_analysis;
    if (res.detected_piece) state.lastDetected = res.detected_piece;
    renderRoomCard(state.lastRoom, state.lastDetected);
    renderCanvas();
    if (state.roomPhoto && !state.outlines.length) fetchOutlines();
    ensureBubbleText(res);
    postOutlineMessage();
    // Only a turn that produced recommendations shows them; later
    // turns (a quote, a question) must not re-post the picks.
    if (res.recommendations && res.recommendations.length) {
      showRecs(res.recommendations);
    }
    // Always re-render: a newer assistant message clears older chips.
    if (!afterQuote(res)) renderOptions(state.lastOptions);
    maybeAutoPreview(res);
  }

  function boxArea(o) {
    var box = o.box || [0, 0, 0, 0];
    return Math.max(0, (box[2] - box[0]) * (box[3] - box[1]));
  }

  function postOutlineMessage() {
    // After the photo is analyzed, the chat gets one item-picker row
    // (thumbnail per detected item + All), once per image. On desktop
    // the same picker sits under the photo, so the chat stays short.
    if (!state.roomPhoto || !isNarrow()) return;
    if (state.outlinePostedFor === state.roomPhoto) return;
    var html = itemPickerHTML();
    if (!html) return;
    var div = document.createElement("div");
    div.className = "msg them outline-msg";
    div.innerHTML = AVATAR + '<div class="chat-outline" dir="auto">' +
      '<p class="chat-outline-cap">' + esc(t("tapToChange")) + "</p>" +
      '<div class="picker-slot">' + html + "</div></div>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    state.outlinePostedFor = state.roomPhoto;
    icons();
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
                                      retries: 1 }).then(function (data) {
        return { data: data, ready: ready };
      });
    })
      .then(function (up) {
        // Room state only commits once the follow-up chat confirms the
        // photo: a chat failure must never leave a broken canvas behind.
        savedPath = up.data.image_path;
        state.outlines = [];
        // Warm the item targets while the chat runs: detection and SAM
        // are independent of the conversation, so the sheet opens ready.
        fetchReq("/api/session/" + encodeURIComponent(state.sessionId) +
                 "/targets?image_path=" + encodeURIComponent(savedPath),
                 { method: "GET", timeoutMs: 120000, retries: 0 })
          .then(function (targets) {
            if (targets && targets.targets &&
                savedPath === state.roomPhoto) {
              state.outlines = targets.targets;
              renderOutlines();
            }
          })
          .catch(function () {});
        return streamChat("", savedPath).then(function (res) {
          if (res) return res;
          // One re-upload: the file may have missed the volume on a
          // fresh container, in which case chat (and its fallback) 400
          // on a path that will never resolve. A new upload gets a new
          // path; failing twice ends the turn like any other failure.
          var fd2 = new FormData();
          fd2.append("file", up.ready, "photo.jpg");
          return fetchReq("/api/upload",
                          { form: fd2, timeoutMs: 60000,
                            retries: 1 }).then(function (data2) {
            savedPath = data2.image_path;
            state.outlines = [];
            return streamChat("", savedPath);
          });
        });
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
          tryFabric(code);
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
      if (!text || state.chatBusy) return;
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
      var ol = e.target && e.target.closest ?
        e.target.closest("[data-outline]") : null;
      if (ol && ol.dataset.outline) {
        selectTarget(ol.dataset.outline, true);
        return;
      }
      // Photo-level resolution: a pointer tap may land inside several
      // nested regions — the smallest one wins, never paint order.
      var oph = e.target && e.target.closest ?
        e.target.closest(".chat-outline-photo") : null;
      if (oph) {
        var taps = oph.querySelectorAll("[data-outline]");
        var best = null, bestArea = Infinity;
        for (var ti = 0; ti < taps.length; ti++) {
          var r = taps[ti].getBoundingClientRect();
          if (e.clientX >= r.left && e.clientX <= r.right &&
              e.clientY >= r.top && e.clientY <= r.bottom) {
            var area = Math.max(0, (r.right - r.left) *
                                  (r.bottom - r.top));
            if (area < bestArea) {
              bestArea = area;
              best = taps[ti];
            }
          }
        }
        if (best && best.dataset.outline) {
          selectTarget(best.dataset.outline, true);
          return;
        }
      }
      var up = e.target && e.target.closest ?
        e.target.closest("[data-upload]") : null;
      if (up) fi.click();
      var tryBtn = e.target && e.target.closest ?
        e.target.closest("[data-try]") : null;
      if (tryBtn && tryBtn.dataset.try) {
        tryFabric(tryBtn.dataset.try, tryBtn.dataset.target || "");
        return;
      }
      var fab = e.target && e.target.closest ?
        e.target.closest("[data-fabric]") : null;
      if (fab && fab.dataset.fabric) openFabricSheet(fab.dataset.fabric);
      var card = e.target && e.target.closest ?
        e.target.closest("#canvasRow .ccard") : null;
      if (card && card.dataset.code) {
        var doneSwap = state.swaps[card.dataset.code];
        if (doneSwap && doneSwap.result_url) openSwapReview(doneSwap);
        else tryFabric(card.dataset.code);
      }
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
      var downAt = 0, pinned = false, wasPinned = false;
      function showBefore(on) {
        var img = $("canvasImg");
        if (!img || !state.roomPhoto) return;
        img.src = on ? "/" + state.roomPhoto.replace(/^\/+/, "")
                     : canvasViewSrc();
      }
      btn.addEventListener("pointerdown", function () {
        downAt = Date.now();
        wasPinned = pinned;
        showBefore(true);
      });
      // Tap toggles, hold peeks. iOS fires pointerleave right after
      // pointerup, so only pointerup decides the toggle.
      btn.addEventListener("pointerup", function () {
        if (Date.now() - downAt < 300) {
          pinned = !wasPinned;
        } else {
          pinned = false;
        }
        showBefore(pinned);
      });
      ["pointerleave", "pointercancel"].forEach(function (ev) {
        btn.addEventListener(ev, function () {
          if (!pinned) showBefore(false);
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
      if (btn && btn.dataset.code) {
        // "View again" shows the finished result; only a real Try
        // starts a new swap.
        if (btn.classList.contains("review") && state.swaps[btn.dataset.code]) {
          openSwapReview(state.swaps[btn.dataset.code]);
          return;
        }
        tryFabric(btn.dataset.code, btn.dataset.target || "");
      }
    });
    messagesEl.addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var thumb = e.target.closest(".swap-thumb");
      if (thumb && thumb.dataset.code && state.swaps[thumb.dataset.code]) {
        openSwapReview(state.swaps[thumb.dataset.code]);
      }
    });
    $("swapTryAgain").addEventListener("click", function () {
      if (state.swapCode) tryFabric(state.swapCode, state.swapTarget,
                                    { noRetry: true });
    });
    $("baRange").addEventListener("input", function (e) {
      baUpdate(Number(e.target.value));
    });
    $("swapClose").addEventListener("click", closeSwap);
    $("swapRetryBtn").addEventListener("click", function () {
      if (state.swapCode) tryFabric(state.swapCode, state.swapTarget);
    });
    $("hoodToggle").addEventListener("click", function () {
      var box = $("swapTrace");
      if (box) box.hidden = !box.hidden;
    });
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
    $("canvasImg").addEventListener("load", renderOutlines);
    $("assignRow").addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var chip = e.target.closest(".assign-chip");
      if (chip && chip.dataset.target) {
        selectTarget(chip.dataset.target, false);
        openBrowse(chip.dataset.target);
        return;
      }
      if (e.target.closest("#applyAllBtn")) {
        runMultiSwap();
        return;
      }
      if (e.target.closest("#resetAssignBtn")) resetAssignments();
    });
    $("browsePanel").addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var btn = e.target.closest("[data-apply]");
      if (btn && btn.dataset.apply) applyBrowse(btn.dataset.apply);
    });
    $("roomView").addEventListener("click", openSheet);
    $("roomThumbBtn").addEventListener("click", openSheet);
    // A just-written volume file can 404 the first GET (deploy
    // handover, sync lag): retry a failed room image once, a beat
    // later, before treating it as broken.
    function retryRoomImg(el, onDead) {
      var cur = el.getAttribute("src") || "";
      if (!cur || cur.indexOf("imgRetry=1") >= 0 ||
          el.dataset.imgRetry === cur) {
        if (onDead) onDead();
        return;
      }
      el.dataset.imgRetry = cur;
      setTimeout(function () {
        el.src = cur + (cur.indexOf("?") < 0 ? "?" : "&") + "imgRetry=1";
      }, 1500);
    }
    $("canvasImg").addEventListener("error", function () {
      retryRoomImg($("canvasImg"));
    });
    $("roomThumb").addEventListener("error", function () {
      retryRoomImg($("roomThumb"), function () {
        var bar = $("roomBar");
        if (bar) bar.hidden = true;
      });
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
    var params = new URLSearchParams(location.search);
    // ?lang= and the landing-page pick are explicit choices: pin them so
    // the very first turn (sample photo or greeting) is in that language
    // instead of leaving it to detection on an empty message.
    var savedLang = null;
    try { savedLang = window.localStorage.getItem("recover_lang"); } catch (e) {}
    if ((params.get("lang") && STRINGS[params.get("lang")]) ||
        (savedLang && STRINGS[savedLang] && savedLang === state.lang)) {
      state.pinned = true;
    }
    var sample = params.get("sample");
    var hasSample = ["living", "majlis", "armchair"].indexOf(sample) >= 0;
    if (params.get("new") === "1") {
      // Landing CTAs start a fresh consultation; the flag is dropped
      // from the URL so a later refresh restores this session instead.
      state.sessionId = newSessionId();
      saveSessionId(state.sessionId);
      params.delete("new");
      try {
        var qs = params.toString();
        window.history.replaceState(null, "", location.pathname +
                                    (qs ? "?" + qs : ""));
      } catch (e) {}
    }
    function startFresh() {
      if (hasSample) {
        // The sample photo IS the first turn: it chats with the image,
        // so analyze runs before the first reply. No imageless greeting.
        state.expectFirst = "sample";
        loadSample(sample);
      } else {
        bootGreeting();
      }
    }
    // A refresh (any URL) restores the stored session first.
    restoreSession().then(function (restored) {
      if (!restored) startFresh();
    });
  }

  function restoreSession() {
    // A page refresh keeps the stored session id: rebuild the chat,
    // photo, picker, picks and last recs from the server.
    var sid = state.sessionId;
    if (!sid) return Promise.resolve(false);
    return fetchReq("/api/session/" + encodeURIComponent(sid) + "/state",
                    { method: "GET", timeoutMs: 15000, retries: 0 })
      .then(function (st) {
        if (!st || sid !== state.sessionId) return false;
        var msgs = st.messages || [];
        if (!msgs.length && !st.image_path) return false;
        if (st.lang && STRINGS[st.lang] && st.lang !== state.lang) {
          state.lang = st.lang;
          state.pinned = true;
          applyI18n();
        }
        state.booted = true;
        chipsEl.hidden = true;
        msgs.forEach(function (m) {
          addMsg(m.text || "", m.who === "me" ? "me" : "them");
        });
        if (st.room_analysis) state.lastRoom = st.room_analysis;
        if (st.detected_piece) {
          state.detectedPiece = st.detected_piece;
          state.lastDetected = st.detected_piece;
        }
        if (st.targets) {
          state.assignments = st.targets.assignments || {};
          state.chosenTargets = st.targets.chosen || [];
          if (state.chosenTargets.length === 1 &&
              SWAP_TARGETS.indexOf(state.chosenTargets[0]) >= 0) {
            state.selectedTarget = state.chosenTargets[0];
          }
        }
        state.lastRecs = st.last_recs || [];
        state.lastOptions = st.options || [];
        state.prevList = (st.previews || []).slice();
        state.swaps = {};
        state.prevList.forEach(function (p) {
          if (p && p.fabric_code) state.swaps[p.fabric_code] = p;
        });
        var lastPrev = state.prevList[state.prevList.length - 1];
        if (st.image_path) {
          state.roomPhoto = st.image_path;
          state.outlinePostedFor = null;
          if (lastPrev && lastPrev.result_url) {
            state.canvasView = "/" + String(lastPrev.result_url)
              .replace(/^\/+/, "");
          }
        }
        renderRoomCard(state.lastRoom, state.lastDetected);
        renderCanvas();
        renderStrip();
        if (state.roomPhoto) fetchOutlines();
        if (state.lastRecs.length) showRecs(state.lastRecs);
        if (st.quoted && st.quote && st.quote.items &&
            st.quote.items.length) {
          postSummaryCard(null, [], st.quote).then(function () {
            renderActionChips(quoteActions(st.quote));
          });
        } else if (state.lastOptions.length) {
          renderOptions(state.lastOptions);
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return true;
      })
      .catch(function () { return false; });
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
