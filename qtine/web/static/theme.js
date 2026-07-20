(function () {
  "use strict";

  var CACHE_KEY = "qtine_theme_cache_v2";
  var BASE = {
    "--p": "#D0BCFF",
    "--op": "#381E72",
    "--pc": "#4F378B",
    "--on-pc": "#EADDFF",
    "--sc": "#4A4458",
    "--bg": "#141218",
    "--sf": "#211F26",
    "--sf-low": "#1D1B20",
    "--sfc": "#2B2930",
    "--on-s": "#E6E1E5",
    "--on-sv": "#CAC4D0",
    "--ol": "#938F99",
    "--olv": "#49454F",
    "--s": "#CCC2DC",
    "--os": "#332D41",
    "--t": "#EFB8C8",
    "--e": "#F2B8B5",
    "--oe": "#601410",
    "--su": "#7DD78D",
    "--w": "#FFD970",
    "--elev1": "0 1px 2px rgba(0,0,0,.3),0 1px 3px 1px rgba(0,0,0,.15)",
    "--rad-s": "8px",
    "--rad-m": "12px",
    "--rad-l": "16px",
    "--rad-xl": "28px",
    "--rad-f": "9999px",
    "--tr": "200ms cubic-bezier(.2,0,0,1)",
    "--mono": "400 13px/20px 'Roboto Mono',monospace"
  };

  function normalize(vars, mode) {
    var merged = {};
    var k;
    for (k in BASE) merged[k] = BASE[k];
    if (vars && typeof vars === "object") {
      for (k in vars) {
        if (Object.prototype.hasOwnProperty.call(vars, k) && /^--[a-z0-9-]+$/i.test(k)) {
          merged[k] = String(vars[k]);
        }
      }
    }
    if (!vars || !vars["--sf-low"]) merged["--sf-low"] = merged["--bg"];
    if (!vars || !vars["--on-pc"]) merged["--on-pc"] = mode === "light" ? merged["--on-s"] : merged["--on-s"];
    return merged;
  }

  function applyTheme(vars, mode) {
    var merged = normalize(vars, mode);
    var styleEl = document.getElementById("qtine-theme-vars");
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "qtine-theme-vars";
      document.head.appendChild(styleEl);
    }
    var css = ":root{";
    for (var k in merged) css += k + ":" + merged[k] + ";";
    css += "color-scheme:" + (mode === "light" ? "light" : "dark") + ";}";
    css += ".btn:hover,.copy-btn:hover,.nav-item:hover,.modal-close:hover,.hero .links a:hover{background:color-mix(in srgb,var(--p) 9%,transparent)}";
    css += ".btn.danger:hover{background:color-mix(in srgb,var(--e) 10%,transparent)}";
    css += ".nav-item.active,.tag-btn.active{background:var(--sc);color:var(--on-s)}";
    css += ".btn.primary{background:var(--p);color:var(--op);border-color:transparent}";
    css += ".btn.primary:hover{background:color-mix(in srgb,var(--p) 88%,var(--on-s))}";
    css += ".card .icon,.detail-head .icon,.contributor .avatar,.contact-item .icon,.hero .version,.msg-item .avatar{background:var(--pc);color:var(--p)}";
    css += ".card.colored{color:var(--p)}";
    css += ".card.colored h3{color:color-mix(in srgb,var(--on-pc) 70%,transparent)}";
    css += ".snackbar{background:var(--sfc);color:var(--on-s);border:1px solid var(--olv)}";
    css += ".log-line .lv-ERROR{color:var(--e)}.log-line .lv-WARNING{color:var(--w)}.log-line .lv-INFO{color:var(--on-s)}.log-line .lv-DEBUG{color:var(--ol)}";
    css += ".chip.ok{background:color-mix(in srgb,var(--su) 15%,transparent)}";
    css += ".chip.err{background:color-mix(in srgb,var(--e) 15%,transparent)}";
    css += ".chip.warn{background:color-mix(in srgb,var(--w) 15%,transparent)}";
    css += ".mirror-item.active{background:color-mix(in srgb,var(--p) 10%,transparent)}";
    styleEl.textContent = css;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", merged["--bg"]);
    return merged;
  }

  function saveCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        name: data.name || "",
        mode: data.mode || "dark",
        variables: data.variables || {}
      }));
    } catch (e) {}
  }

  function applyCachedTheme() {
    try {
      var cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      if (cached && cached.variables) applyTheme(cached.variables, cached.mode);
    } catch (e) {}
  }

  function loadTheme() {
    return fetch("/api/themes/current", { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (d) {
        if (!d || !d.variables) return null;
        applyTheme(d.variables, d.mode);
        saveCache(d);
        return d;
      })
      .catch(function () { return null; });
  }

  applyCachedTheme();

  window.QtineTheme = {
    apply: function (vars, mode, name) {
      var merged = applyTheme(vars, mode);
      saveCache({ name: name || "", mode: mode || "dark", variables: merged });
      return merged;
    },
    reload: loadTheme,
    clear: function () {
      try { localStorage.removeItem(CACHE_KEY); } catch (e) {}
    }
  };

  loadTheme();
})();
