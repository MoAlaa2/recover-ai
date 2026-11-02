/* ReCover shared helpers (no build step): client-side photo prep and
   the one money formatter. Loaded before app.js / designer.js. */
window.RC = (function () {
  "use strict";

  var MAX_EDGE = 2048, JPEG_Q = 0.88;

  function canvasToJpeg(canvas, fallback) {
    function viaDataURL() {
      try {
        var parts = canvas.toDataURL("image/jpeg", JPEG_Q).split(",");
        var bin = atob(parts[1]);
        var arr = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        return new Blob([arr], { type: "image/jpeg" });
      } catch (e) { return null; }
    }
    return new Promise(function (resolve) {
      if (canvas.toBlob) {
        try {
          canvas.toBlob(function (blob) {
            resolve(blob || viaDataURL() || fallback);
          }, "image/jpeg", JPEG_Q);
          return;
        } catch (e) {}
      }
      resolve(viaDataURL() || fallback);
    });
  }

  function drawScaled(source, w, h) {
    var scale = Math.min(1, MAX_EDGE / Math.max(w, h));
    var canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(w * scale));
    canvas.height = Math.max(1, Math.round(h * scale));
    canvas.getContext("2d").drawImage(source, 0, 0, canvas.width,
                                      canvas.height);
    return canvas;
  }

  // createImageBitmap honours EXIF with imageOrientation: "from-image".
  function viaBitmap(file) {
    if (typeof createImageBitmap === "undefined") {
      return Promise.reject(new Error("no createImageBitmap"));
    }
    var p;
    try {
      p = createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (e) {
      p = null;
    }
    if (!p || !p.then) {
      try { p = createImageBitmap(file); } catch (e2) {
        return Promise.reject(e2);
      }
    }
    return p.then(function (bmp) {
      if (!bmp.width || !bmp.height) throw new Error("empty bitmap");
      var canvas = drawScaled(bmp, bmp.width, bmp.height);
      if (bmp.close) bmp.close();
      return canvas;
    });
  }

  // Safari decodes HEIC in <img> even where createImageBitmap refuses
  // the blob; <img> already applies EXIF orientation (image-orientation:
  // from-image is the default), so the canvas copy comes out upright.
  function viaImg(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      var done = false;
      function finish(ok) {
        if (done) return;
        done = true;
        URL.revokeObjectURL(url);
        if (!ok || !img.naturalWidth) {
          reject(new Error("img decode failed"));
          return;
        }
        try {
          resolve(drawScaled(img, img.naturalWidth, img.naturalHeight));
        } catch (e) { reject(e); }
      }
      img.onload = function () {
        if (img.decode) {
          img.decode().then(function () { finish(true); },
                            function () { finish(true); });
        } else finish(true);
      };
      img.onerror = function () { finish(false); };
      setTimeout(function () { finish(false); }, 20000);
      img.src = url;
    });
  }

  function isImage(file) {
    var type = (file && file.type) || "";
    var name = (file && file.name) || "";
    return type.indexOf("image/") === 0 ||
      /\.(heic|heif|jpe?g|png|webp|gif|bmp|tiff?)$/i.test(name);
  }

  // Resolves to a JPEG Blob (long edge <= 2048 px, quality 0.88), or
  // the untouched file when nothing in the browser could decode it.
  function prepareImage(file) {
    if (!file || !isImage(file)) return Promise.resolve(file);
    return viaBitmap(file)
      .catch(function () { return viaImg(file); })
      .then(function (canvas) { return canvasToJpeg(canvas, file); })
      .catch(function () { return file; });
  }

  function arabicDigits(text) {
    return String(text).replace(/[0-9]/g, function (d) {
      return "٠١٢٣٤٥٦٧٨٩"[+d];
    });
  }

  // "$1,090.50", "$155": separators always, cents only when present.
  function money(value, lang, opts) {
    if (value === undefined || value === null || value === "") return "";
    var n = Number(value);
    if (isNaN(n)) return String(value);
    var cents = Math.round(n * 100);
    var whole = Math.floor(Math.abs(cents) / 100);
    var frac = Math.abs(cents) % 100;
    var text = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    if (frac) text += "." + (frac < 10 ? "0" : "") + frac;
    if (cents < 0) text = "-" + text;
    if (lang === "ar") text = arabicDigits(text);
    var symbol = !(opts && opts.symbol === false);
    return symbol ? "$" + text : text;
  }

  return { prepareImage: prepareImage, money: money,
           arabicDigits: arabicDigits, MAX_EDGE: MAX_EDGE,
           JPEG_QUALITY: JPEG_Q };
})();
