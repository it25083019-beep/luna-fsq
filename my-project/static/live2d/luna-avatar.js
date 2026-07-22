/**
 * LUNA sprite avatar — expression + blink + lip-sync until Live2D PSD is ready.
 */
(function (global) {
  const BASE = "/static/live2d/luna-expressions";
  const EXPRESSIONS = {
    neutral: `${BASE}/luna-neutral.png`,
    talk: `${BASE}/luna-talk.png`,
    blink: `${BASE}/luna-blink.png`,
    cheer: `${BASE}/luna-cheer.png`,
    wave: `${BASE}/luna-wave.png`,
    think: `${BASE}/luna-think.png`,
    sad: `${BASE}/luna-sad.png`,
    surprised: `${BASE}/luna-surprised.png`,
    happy: `${BASE}/luna-happy.png`,
  };

  const SITUATION_RULES = [
    { expr: "wave", patterns: [/こんにちは|おはよう|こんばんは|やあ|はじめまして|ようこそ|hello|hi\b/i] },
    { expr: "cheer", patterns: [/がんば|頑張|できた|すごい|ナイス|よくでき|おめでと|合格|クリア|すばらし|いいね|えらい|拍手/i] },
    { expr: "sad", patterns: [/つらい|悲し|残念|ごめん|申し訳|しんどい|不安|心配/i] },
    { expr: "think", patterns: [/どうして|なぜ|考え|教えて|どうすれば|？|\?/] },
    { expr: "surprised", patterns: [/えっ|まじ|びっくり|本当に|！？|驚/i] },
    { expr: "happy", patterns: [/ありがと|嬉し|楽し|うれし|笑|ワクワク|やった/i] },
  ];

  function detectExpression(text, opts = {}) {
    const t = String(text || "");
    if (opts.greeting) return "wave";
    for (const rule of SITUATION_RULES) {
      if (rule.patterns.some((re) => re.test(t))) return rule.expr;
    }
    return opts.fallback || "neutral";
  }

  class LunaAvatar {
    constructor(imgEl, statusEl) {
      this.img = imgEl;
      this.statusEl = statusEl;
      this.current = "neutral";
      this.blinkTimer = null;
      this.lipTimer = null;
      this.exprTimer = null;
      this.speaking = false;
      this._preload();
      this.setExpression("neutral");
      this.startBlink();
    }

    _preload() {
      Object.values(EXPRESSIONS).forEach((src) => {
        const img = new Image();
        img.src = src;
      });
    }

    _setStatus(msg) {
      if (this.statusEl) this.statusEl.textContent = msg;
    }

    setExpression(name, holdMs = 0) {
      const key = EXPRESSIONS[name] ? name : "neutral";
      this.current = key;
      if (this.img) {
        this.img.src = EXPRESSIONS[key];
        this.img.alt = `LUNA — ${key}`;
      }
      if (this.exprTimer) {
        clearTimeout(this.exprTimer);
        this.exprTimer = null;
      }
      if (holdMs > 0) {
        this.exprTimer = setTimeout(() => {
          if (!this.speaking) this.setExpression("neutral");
        }, holdMs);
      }
      return key;
    }

    playExpression(name, holdMs = 2200) {
      if (this.speaking && name !== "talk" && name !== "blink") return;
      this.setExpression(name, holdMs);
    }

    reactToText(text, opts = {}) {
      const expr = detectExpression(text, opts);
      const hold = expr === "wave" ? 2800 : expr === "cheer" ? 2600 : 2200;
      this.playExpression(expr, hold);
      return expr;
    }

    startBlink() {
      this.stopBlink();
      const schedule = () => {
        const delay = 2800 + Math.random() * 3200;
        this.blinkTimer = setTimeout(() => {
          if (!this.speaking && this.current === "neutral") {
            this.setExpression("blink");
            setTimeout(() => {
              if (!this.speaking && this.current === "blink") this.setExpression("neutral");
            }, 120 + Math.random() * 80);
          }
          schedule();
        }, delay);
      };
      schedule();
    }

    stopBlink() {
      if (this.blinkTimer) clearTimeout(this.blinkTimer);
      this.blinkTimer = null;
    }

    startLipSync() {
      this.stopLipSync();
      this.speaking = true;
      let open = false;
      this.lipTimer = setInterval(() => {
        open = !open;
        this.setExpression(open ? "talk" : "neutral");
      }, 90 + Math.random() * 50);
    }

    stopLipSync() {
      this.speaking = false;
      if (this.lipTimer) clearInterval(this.lipTimer);
      this.lipTimer = null;
      this.setExpression("neutral");
    }

    destroy() {
      this.stopBlink();
      this.stopLipSync();
      if (this.exprTimer) clearTimeout(this.exprTimer);
    }

    async init() {
      this._setStatus("LUNA 表情スプライト OK — まばたき・口パク・状況別リアクション");
      return true;
    }
  }

  global.LunaAvatar = LunaAvatar;
  global.LunaExpressions = Object.keys(EXPRESSIONS);
  global.detectLunaExpression = detectExpression;
})(window);
