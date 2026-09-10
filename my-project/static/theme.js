/** Shared theme presets for LUNA / FSQ (localStorage: luna_theme) */
(function (global) {
  const KEY = "luna_theme";
  const THEMES = {
    fsq: {
      id: "fsq",
      label: "FSQナイト",
      swatch: ["#10153d", "#4e7cff", "#ffc857"],
      vars: {
        "--bg0": "#10153d",
        "--bg1": "#16276a",
        "--bg2": "#5b36b8",
        "--card": "rgba(255,255,255,.96)",
        "--text": "#22265a",
        "--muted": "#717594",
        "--lilac": "#4e7cff",
        "--lilac-deep": "#8a5cf6",
        "--pink": "#ff6fae",
        "--mint": "#32c48d",
        "--amber": "#ffc857",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px rgba(28,32,91,.18)",
        "--input-bg": "#eef0ff",
        "--ghost-bg": "#e8eaff",
        "--composer-bg": "#ffffff",
        "--glow-a": "rgba(94,140,255,.35)",
        "--glow-b": "rgba(177,92,255,.28)",
        "--st1": "linear-gradient(160deg,#efe6ff,#fff)",
        "--st2": "linear-gradient(160deg,#e4f4ff,#fff)",
        "--st3": "linear-gradient(160deg,#ffe8f2,#fff)",
        "--hero-top": "#080d34",
        "--hero-mid": "#17115b",
        "--nav-bg": "rgba(255,255,255,.97)",
        "--nav-active": "#4e7cff",
        "--nav-idle": "#7c819e",
        "--panel-light": "#f6f7ff",
      },
      themeColor: "#17115b",
    },
    lilac: {
      id: "lilac",
      label: "ライラック",
      swatch: ["#e8dff7", "#9b7ed9", "#f0a8c8"],
      vars: {
        "--bg0": "#e8dff7",
        "--bg1": "#d4e8f8",
        "--bg2": "#f7e6f0",
        "--card": "rgba(255,255,255,.88)",
        "--text": "#4a3b6b",
        "--muted": "#8a7aa8",
        "--lilac": "#9b7ed9",
        "--lilac-deep": "#7b5eb8",
        "--pink": "#f0a8c8",
        "--mint": "#6ec9b8",
        "--amber": "#e8b86d",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px rgba(120, 90, 180, .14)",
        "--input-bg": "#f6f1fc",
        "--ghost-bg": "#efe8f8",
        "--composer-bg": "#ffffff",
        "--glow-a": "rgba(240,168,200,.35)",
        "--glow-b": "rgba(155,126,217,.28)",
        "--st1": "linear-gradient(160deg,#efe6ff,#fff)",
        "--st2": "linear-gradient(160deg,#e4f4ff,#fff)",
        "--st3": "linear-gradient(160deg,#ffe8f2,#fff)",
        "--hero-top": "#6b5a9a",
        "--hero-mid": "#9b7ed9",
        "--nav-bg": "rgba(255,255,255,.96)",
        "--nav-active": "#7b5eb8",
        "--nav-idle": "#8a7aa8",
        "--panel-light": "#faf7ff",
      },
      themeColor: "#c9b6e8",
    },
    mint: {
      id: "mint",
      label: "ミント",
      swatch: ["#d9f3ee", "#5bb8a8", "#9fd4c8"],
      vars: {
        "--bg0": "#d9f3ee",
        "--bg1": "#e4f0fb",
        "--bg2": "#eef8e8",
        "--card": "rgba(255,255,255,.9)",
        "--text": "#2f4f4a",
        "--muted": "#6f8f88",
        "--lilac": "#5bb8a8",
        "--lilac-deep": "#3d8f82",
        "--pink": "#9fd4c8",
        "--mint": "#5bb8a8",
        "--amber": "#e0b36a",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px rgba(60, 140, 120, .14)",
        "--input-bg": "#eef8f5",
        "--ghost-bg": "#dff3ee",
        "--composer-bg": "#ffffff",
        "--glow-a": "rgba(91,184,168,.32)",
        "--glow-b": "rgba(110,201,184,.22)",
        "--st1": "linear-gradient(160deg,#dff8f2,#fff)",
        "--st2": "linear-gradient(160deg,#e4f4ff,#fff)",
        "--st3": "linear-gradient(160deg,#eef8e8,#fff)",
        "--hero-top": "#1a4a44",
        "--hero-mid": "#3d8f82",
        "--nav-bg": "rgba(255,255,255,.96)",
        "--nav-active": "#3d8f82",
        "--nav-idle": "#6f8f88",
        "--panel-light": "#f4fbf9",
      },
      themeColor: "#9fd4c8",
    },
    peach: {
      id: "peach",
      label: "ピーチ",
      swatch: ["#ffe8df", "#e89a8a", "#f0a8b8"],
      vars: {
        "--bg0": "#ffe8df",
        "--bg1": "#ffeef5",
        "--bg2": "#fff3e0",
        "--card": "rgba(255,255,255,.9)",
        "--text": "#6b3f3f",
        "--muted": "#a88888",
        "--lilac": "#e89a8a",
        "--lilac-deep": "#d47878",
        "--pink": "#f0a8b8",
        "--mint": "#e8b86d",
        "--amber": "#e8b86d",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px rgba(180, 100, 90, .14)",
        "--input-bg": "#fff4ef",
        "--ghost-bg": "#ffe8e0",
        "--composer-bg": "#ffffff",
        "--glow-a": "rgba(232,154,138,.35)",
        "--glow-b": "rgba(240,168,184,.28)",
        "--st1": "linear-gradient(160deg,#ffe8df,#fff)",
        "--st2": "linear-gradient(160deg,#ffeef5,#fff)",
        "--st3": "linear-gradient(160deg,#fff3e0,#fff)",
        "--hero-top": "#6b3f3f",
        "--hero-mid": "#d47878",
        "--nav-bg": "rgba(255,255,255,.96)",
        "--nav-active": "#d47878",
        "--nav-idle": "#a88888",
        "--panel-light": "#fff8f5",
      },
      themeColor: "#f0c0b0",
    },
    sky: {
      id: "sky",
      label: "スカイ",
      swatch: ["#dcecff", "#6aa7e0", "#a8c8f0"],
      vars: {
        "--bg0": "#dcecff",
        "--bg1": "#e8f4ff",
        "--bg2": "#eef0ff",
        "--card": "rgba(255,255,255,.9)",
        "--text": "#35506b",
        "--muted": "#7a92a8",
        "--lilac": "#6aa7e0",
        "--lilac-deep": "#4a86c0",
        "--pink": "#a8c8f0",
        "--mint": "#6ec9b8",
        "--amber": "#e8b86d",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px rgba(80, 120, 180, .14)",
        "--input-bg": "#eef5ff",
        "--ghost-bg": "#e0ecff",
        "--composer-bg": "#ffffff",
        "--glow-a": "rgba(106,167,224,.32)",
        "--glow-b": "rgba(168,200,240,.28)",
        "--st1": "linear-gradient(160deg,#e0ecff,#fff)",
        "--st2": "linear-gradient(160deg,#e8f4ff,#fff)",
        "--st3": "linear-gradient(160deg,#eef0ff,#fff)",
        "--hero-top": "#1e3a5f",
        "--hero-mid": "#4a86c0",
        "--nav-bg": "rgba(255,255,255,.96)",
        "--nav-active": "#4a86c0",
        "--nav-idle": "#7a92a8",
        "--panel-light": "#f5f9ff",
      },
      themeColor: "#a8c8f0",
    },
    night: {
      id: "night",
      label: "ナイト",
      swatch: ["#0c1416", "#2ec4b6", "#e8b86d"],
      vars: {
        "--bg0": "#0c1416",
        "--bg1": "#122024",
        "--bg2": "#0a1214",
        "--card": "rgba(22,33,38,.92)",
        "--text": "#e8f0ef",
        "--muted": "#8aa3a0",
        "--lilac": "#2ec4b6",
        "--lilac-deep": "#e8b86d",
        "--pink": "#2ec4b6",
        "--mint": "#2ec4b6",
        "--amber": "#e8b86d",
        "--danger": "#d96b6b",
        "--shadow": "0 12px 32px rgba(0,0,0,.35)",
        "--input-bg": "#1a2a2e",
        "--ghost-bg": "#1e3034",
        "--composer-bg": "#162126",
        "--glow-a": "rgba(46,196,182,.18)",
        "--glow-b": "rgba(232,184,109,.12)",
        "--st1": "linear-gradient(160deg,#1a2e32,#162126)",
        "--st2": "linear-gradient(160deg,#1a2830,#162126)",
        "--st3": "linear-gradient(160deg,#2a2420,#162126)",
        "--hero-top": "#0c1416",
        "--hero-mid": "#122024",
        "--nav-bg": "rgba(14,20,24,.98)",
        "--nav-active": "#2ec4b6",
        "--nav-idle": "#8aa3a0",
        "--panel-light": "#122024",
      },
      themeColor: "#0c1416",
    },
  };

  const HUE_KEY = "luna_theme_hue";

  function clampHue(h) {
    const n = Number(h);
    if (!Number.isFinite(n)) return 258;
    return ((Math.round(n) % 360) + 360) % 360;
  }

  function hsl(h, s, l, a) {
    const hue = clampHue(h);
    if (a == null) return "hsl(" + hue + " " + s + "% " + l + "%)";
    return "hsl(" + hue + " " + s + "% " + l + "% / " + a + ")";
  }

  function spriteVarsFor(id) {
    if (id === "night") {
      return {
        "--sprite-glow": "rgba(220,255,248,.82)",
        "--sprite-outline": "rgba(255,255,255,.96)",
      };
    }
    if (id === "fsq") {
      return {
        "--sprite-glow": "rgba(255,244,220,.88)",
        "--sprite-outline": "rgba(255,255,255,.97)",
      };
    }
    return {
      "--sprite-glow": "rgba(255,252,248,.55)",
      "--sprite-outline": "rgba(255,255,255,.75)",
    };
  }

  function currentHue() {
    try {
      const saved = localStorage.getItem(HUE_KEY);
      if (saved != null && saved !== "") return clampHue(saved);
    } catch (_) {}
    return 258;
  }

  function hueToHex(h) {
    h = clampHue(h);
    const s = 0.58;
    const l = 0.52;
    const a = s * Math.min(l, 1 - l);
    const f = (n) => {
      const k = (n + h / 30) % 12;
      const c = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
      return Math.round(255 * c)
        .toString(16)
        .padStart(2, "0");
    };
    return "#" + f(0) + f(8) + f(4);
  }

  function hexToHue(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
    if (!m) return currentHue();
    const n = parseInt(m[1], 16);
    const r = ((n >> 16) & 255) / 255;
    const g = ((n >> 8) & 255) / 255;
    const b = (n & 255) / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    if (max === min) return 0;
    const d = max - min;
    let h = 0;
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
    return Math.round(h);
  }

  function themeFromHue(h) {
    h = clampHue(h);
    const h2 = (h + 28) % 360;
    const h3 = (h + 332) % 360;
    return {
      id: "custom",
      label: "カスタム",
      swatch: [hsl(h, 32, 90), hsl(h, 55, 58), hsl(h2, 50, 62)],
      vars: {
        "--bg0": hsl(h, 38, 92),
        "--bg1": hsl(h2, 32, 91),
        "--bg2": hsl(h3, 34, 92),
        "--card": "rgba(255,255,255,.92)",
        "--text": hsl(h, 32, 24),
        "--muted": hsl(h, 14, 48),
        "--lilac": hsl(h, 55, 58),
        "--lilac-deep": hsl(h, 48, 42),
        "--pink": hsl(h3, 52, 72),
        "--mint": hsl((h + 140) % 360, 42, 52),
        "--amber": "hsl(38 70% 62%)",
        "--danger": "#e07a8a",
        "--shadow": "0 12px 32px " + hsl(h, 40, 30, 0.16),
        "--input-bg": hsl(h, 36, 96),
        "--ghost-bg": hsl(h, 30, 93),
        "--composer-bg": "#ffffff",
        "--glow-a": hsl(h, 70, 70, 0.35),
        "--glow-b": hsl(h2, 60, 68, 0.28),
        "--st1": "linear-gradient(160deg," + hsl(h, 40, 94) + ",#fff)",
        "--st2": "linear-gradient(160deg," + hsl(h2, 40, 94) + ",#fff)",
        "--st3": "linear-gradient(160deg," + hsl(h3, 40, 94) + ",#fff)",
        "--hero-top": hsl(h, 42, 22),
        "--hero-mid": hsl(h, 40, 36),
        "--nav-bg": "rgba(255,255,255,.97)",
        "--nav-active": hsl(h, 48, 42),
        "--nav-idle": hsl(h, 12, 48),
        "--panel-light": hsl(h, 30, 97),
        "--sprite-glow": hsl(h, 40, 96, 0.88),
        "--sprite-outline": "rgba(255,255,255,.95)",
      },
      themeColor: hsl(h, 40, 36),
    };
  }

  function paint(theme) {
    const root = document.documentElement;
    const extra = theme.id === "custom" ? {} : spriteVarsFor(theme.id);
    Object.entries(Object.assign({}, extra, theme.vars)).forEach(([k, v]) => root.style.setProperty(k, v));
    root.dataset.theme = theme.id;
    root.style.setProperty("--hue", String(currentHue()));
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme.themeColor);
  }

  function applyCustomHue(h) {
    h = clampHue(h);
    try {
      localStorage.setItem(HUE_KEY, String(h));
      localStorage.setItem(KEY, "custom");
    } catch (_) {}
    const theme = themeFromHue(h);
    const root = document.documentElement;
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    root.dataset.theme = "custom";
    root.style.setProperty("--hue", String(h));
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme.themeColor);
    document.dispatchEvent(new CustomEvent("luna-theme", { detail: "custom" }));
    return "custom";
  }

  function applyTheme(id) {
    if (id === "custom") return applyCustomHue(currentHue());
    const theme = THEMES[id] || THEMES.lilac;
    paint(theme);
    try {
      localStorage.setItem(KEY, theme.id);
    } catch (_) {}
    document.dispatchEvent(new CustomEvent("luna-theme", { detail: theme.id }));
    return theme.id;
  }

  function currentTheme() {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "custom") return "custom";
      if (saved && THEMES[saved]) return saved;
      return "lilac";
    } catch (_) {
      return "lilac";
    }
  }

  function boot() {
    applyTheme(currentTheme());
  }

  global.LunaTheme = {
    THEMES,
    applyTheme,
    applyCustomHue,
    currentTheme,
    currentHue,
    hueToHex,
    hexToHue,
    boot,
    KEY,
    HUE_KEY,
  };
})(window);
