/**
 * LUNA 2D avatar — expression / idle / tap / lip-sync / thinking
 */
(function (global) {
  const BASE = "/static/live2d/luna-expressions";

  const EMOTION_MAP = {
    neutral: "neutral",
    joy: "happy",
    happy: "happy",
    sadness: "sad",
    sad: "sad",
    surprise: "surprised",
    surprised: "surprised",
    think: "think",
    cheer: "cheer",
    wave: "wave",
  };

  const EXPRESSIONS = {
    neutral: `${BASE}/luna-neutral.png`,
    happy: `${BASE}/luna-happy.png`,
    sad: `${BASE}/luna-sad.png`,
    surprised: `${BASE}/luna-surprised.png`,
    talk: `${BASE}/luna-talk.png`,
    blink: `${BASE}/luna-blink.png`,
    wave: `${BASE}/luna-wave.png`,
    cheer: `${BASE}/luna-cheer.png`,
    think: `${BASE}/luna-think.png`,
  };

  const TAP_MOTIONS = ["happy", "cheer", "wave", "surprised"];

  function mapEmotion(emotion) {
    if (!emotion) return "neutral";
    const k = String(emotion).toLowerCase().trim();
    return EMOTION_MAP[k] || (EXPRESSIONS[k] ? k : "neutral");
  }

  function detectExpression(text, opts = {}) {
    const t = (text || "").trim();
    if (opts.greeting) return "wave";
    if (opts.fallback === "think") return "think";
    if (opts.fallback === "sad") return "sad";
    if (opts.fallback === "happy") return "happy";
    const rules = [
      { expr: "cheer", patterns: [/やった|すごい|がんば|応援|クリア|成功|おめでとう/] },
      { expr: "wave", patterns: [/こんにちは|おはよう|こんばんは|はじめまして|よろしく/] },
      { expr: "sad", patterns: [/つらい|悲しい|落ち込|疲れ|ごめん|大丈夫？/] },
      { expr: "surprised", patterns: [/えっ|まさか|びっくり|すごい！|！{2,}/] },
      { expr: "think", patterns: [/どうして|なぜ|考え|教えて|どうすれば|？|\?/] },
      { expr: "happy", patterns: [/嬉しい|楽しい|いいね|大好き|ありがとう/] },
    ];
    for (const r of rules) {
      if (r.patterns.some((p) => p.test(t))) return r.expr;
    }
    const tag = t.match(/^\[(neutral|joy|happy|sadness|sad|surprise|surprised|think|cheer|wave)\]/i);
    if (tag) return mapEmotion(tag[1]);
    return opts.fallback || "happy";
  }

  class LunaAvatar {
    /**
     * @param {HTMLImageElement} imgEl
     * @param {HTMLElement|null} statusEl
     * @param {HTMLElement|null} stageEl — wrapper for CSS idle/tap motion
     */
    constructor(imgEl, statusEl, stageEl) {
      this.img = imgEl;
      this.statusEl = statusEl || null;
      this.stage = stageEl || (imgEl && imgEl.parentElement) || null;
      this.current = "neutral";
      this.blinkTimer = null;
      this.lipTimer = null;
      this.exprTimer = null;
      this.idleTimer = null;
      this.speaking = false;
      this.thinking = false;
      this._preload();
      this.setExpression("neutral");
      this.startBlink();
      this.startIdle();
      if (this.stage) {
        this.stage.classList.add("luna-stage");
        this.stage.addEventListener("click", () => this.tap());
        this.stage.style.cursor = "pointer";
        this.stage.title = "タップでリアクション";
      }
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

    _setMotionClass(name) {
      if (!this.stage) return;
      this.stage.classList.remove(
        "luna-idle",
        "luna-bob",
        "luna-wave-motion",
        "luna-cheer-motion",
        "luna-talk-motion",
        "luna-tap-bounce",
        "luna-think-motion"
      );
      if (name) this.stage.classList.add(name);
    }

    setExpression(name, holdMs = 0) {
      const key = EXPRESSIONS[name] ? name : mapEmotion(name);
      this.current = EXPRESSIONS[key] ? key : "neutral";
      if (this.img) {
        this.img.src = EXPRESSIONS[this.current];
        this.img.alt = `LUNA — ${this.current}`;
        this.img.classList.remove("luna-fade");
        void this.img.offsetWidth;
        this.img.classList.add("luna-fade");
      }
      if (this.thinking) this._setMotionClass("luna-think-motion");
      else if (this.current === "wave") this._setMotionClass("luna-wave-motion");
      else if (this.current === "cheer") this._setMotionClass("luna-cheer-motion");
      else if (this.current === "talk" || this.speaking) this._setMotionClass("luna-talk-motion");
      else if (!this.speaking) this._setMotionClass("luna-idle");

      if (this.exprTimer) {
        clearTimeout(this.exprTimer);
        this.exprTimer = null;
      }
      if (holdMs > 0 && !this.thinking) {
        this.exprTimer = setTimeout(() => {
          if (!this.speaking && !this.thinking) this.setExpression("neutral");
        }, holdMs);
      }
      return this.current;
    }

    playExpression(name, holdMs = 2200) {
      if (this.thinking && name !== "think") return;
      if (this.speaking && name !== "talk" && name !== "blink") return;
      this.setExpression(name, holdMs);
    }

    /** Keep think pose until stopThinking() — while waiting for chat reply. */
    startThinking() {
      this.thinking = true;
      this.speaking = false;
      if (this.lipTimer) {
        clearInterval(this.lipTimer);
        this.lipTimer = null;
      }
      if (this.exprTimer) {
        clearTimeout(this.exprTimer);
        this.exprTimer = null;
      }
      this.setExpression("think", 0);
      this._setMotionClass("luna-think-motion");
    }

    stopThinking() {
      if (!this.thinking) return;
      this.thinking = false;
      if (!this.speaking) {
        this.setExpression("neutral");
        this._setMotionClass("luna-idle");
      }
    }

    applyEmotion(emotion, holdMs = 2400) {
      if (this.thinking) this.stopThinking();
      const key = mapEmotion(emotion);
      this.playExpression(key, holdMs);
      return key;
    }

    reactToText(text, opts = {}) {
      if (this.thinking && !(opts && opts.force)) return "think";
      const expr = detectExpression(text, opts);
      const hold = expr === "wave" ? 2800 : expr === "cheer" ? 2600 : 2200;
      this.playExpression(expr, hold);
      return expr;
    }

    tap() {
      if (this.speaking || this.thinking) return;
      const pick = TAP_MOTIONS[Math.floor(Math.random() * TAP_MOTIONS.length)];
      this._setMotionClass("luna-tap-bounce");
      this.playExpression(pick, 2000);
    }

    startIdle() {
      this.stopIdle();
      this._setMotionClass("luna-idle");
      this.idleTimer = setInterval(() => {
        if (this.speaking || this.thinking || !this.stage) return;
        if (this.current !== "neutral" && this.current !== "blink") return;
        this.stage.classList.add("luna-bob");
        setTimeout(() => this.stage && this.stage.classList.remove("luna-bob"), 900);
      }, 5000 + Math.random() * 4000);
    }

    stopIdle() {
      if (this.idleTimer) clearInterval(this.idleTimer);
      this.idleTimer = null;
    }

    startBlink() {
      this.stopBlink();
      const schedule = () => {
        const delay = 2800 + Math.random() * 3200;
        this.blinkTimer = setTimeout(() => {
          if (!this.speaking && !this.thinking && (this.current === "neutral" || this.current === "happy")) {
            const prev = this.current;
            this.setExpression("blink");
            setTimeout(() => {
              if (!this.speaking && !this.thinking && this.current === "blink") {
                this.setExpression(prev === "happy" ? "happy" : "neutral");
              }
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
      this.stopThinking();
      this.stopLipSync();
      this.speaking = true;
      this._setMotionClass("luna-talk-motion");
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
      if (this.thinking) {
        this.setExpression("think", 0);
        this._setMotionClass("luna-think-motion");
        return;
      }
      this.setExpression("neutral");
      this._setMotionClass("luna-idle");
    }

    destroy() {
      this.stopBlink();
      this.stopLipSync();
      this.stopIdle();
      this.thinking = false;
      if (this.exprTimer) clearTimeout(this.exprTimer);
    }

    async init() {
      this._setStatus("LUNA 2D — emotionMap / idle / tap / lip-sync");
      return true;
    }
  }

  global.LunaAvatar = LunaAvatar;
  global.LunaExpressions = Object.keys(EXPRESSIONS);
  global.LunaEmotionMap = EMOTION_MAP;
  global.detectLunaExpression = detectExpression;
})(window);
