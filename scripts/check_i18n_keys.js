/* i18n parity: every consult-app + landing key present in en must
   exist in ar/hi/fr/es (t() falls back to English otherwise), and
   every FEATURE/RELAX label must cover all five languages. */
var fs = require("fs");

function leaves(o, prefix, out) {
  for (var k in o) {
    var v = o[k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      leaves(v, prefix + k + ".", out);
    } else {
      out.push(prefix + k);
    }
  }
  return out;
}

var failures = 0;
function check(name, packs, langs) {
  var base = {};
  leaves(packs.en, "", []).forEach(function (k) { base[k] = 1; });
  langs.forEach(function (L) {
    var mine = {};
    leaves(packs[L] || {}, "", []).forEach(function (k) { mine[k] = 1; });
    Object.keys(base).forEach(function (k) {
      if (!mine[k]) {
        console.log("MISS %s %s %s", name, L, k);
        failures++;
      }
    });
  });
}

function checkLabels(name, table, langs) {
  Object.keys(table).forEach(function (k) {
    var v = table[k];
    if (!Array.isArray(v) || v.length < langs.length) {
      console.log("SHORT %s %s (%d/%d)", name, k,
                  Array.isArray(v) ? v.length : -1, langs.length);
      failures++;
      return;
    }
    v.forEach(function (s, i) {
      if (typeof s !== "string" || !s.length) {
        console.log("EMPTY %s %s [%d]", name, k, i);
        failures++;
      }
    });
  });
}

var appSrc = fs.readFileSync("app/static/app.js", "utf8");
var a0 = appSrc.indexOf("var STRINGS = ") + 14;
var a1 = appSrc.indexOf("\n  };", a0) + 4;
var STRINGS = eval("(" + appSrc.slice(a0, a1) + ")");
check("consult", STRINGS, ["ar", "hi", "fr", "es"]);

var landSrc = fs.readFileSync("app/static/strings.js", "utf8");
var lm = landSrc.match(/window\.RC_STRINGS = (\{[\s\S]*\});/);
var LAND = eval("(" + lm[1] + ")");
check("landing", LAND, ["ar", "hi", "fr", "es"]);

var f0 = appSrc.indexOf("var FEATURE_LABELS = ") +
  "var FEATURE_LABELS = ".length;
var f1 = appSrc.indexOf("\n  };", f0) + 4;
var FEATURE_LABELS = eval("(" + appSrc.slice(f0, f1) + ")");
checkLabels("features", FEATURE_LABELS, ["en", "ar", "hi", "fr", "es"]);

var r0 = appSrc.indexOf("var RELAX_LABELS = ") +
  "var RELAX_LABELS = ".length;
var r1 = appSrc.indexOf("\n  };", r0) + 4;
var RELAX_LABELS = eval("(" + appSrc.slice(r0, r1) + ")");
checkLabels("relax", RELAX_LABELS, ["en", "ar", "hi", "fr", "es"]);

if (failures) {
  console.log("i18n parity FAILED: %d", failures);
  process.exit(1);
}
console.log("i18n parity OK");
