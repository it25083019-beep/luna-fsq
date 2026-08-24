/**
 * LUNA 2D avatar — VTuber-inspired emotionMap + idle/tap motions (sprite stage).
 * Pattern from Open-LLM-VTuber: emotion tags → expression, idle loop, tap motions.
 */
(function (global) {
  const BASE = "/static/live2d/luna-expressions";

  /** emotionMap (Open-LLM-VTuber style) → sprite key */
  const EMOTION_MAP = {
    neutral: "neutral",
    joy: "happy",
    happy: "happy",
    smirk: "happy",
    cheer: "cheer",
    wave: "wave",
    sadness: "sad",
    sad: "sad",
    fear: "sad",
    disgust: "sad",
    anger: "surprised",
    surprise: "surprised",
    surprised: "surprised",
    think: "think",
    talk: "talk",
    blink: "blink",
  };

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

  const TAP_MOTIONS = ["wave", "cheer", "happy", "surprised"];

  const SITUATION_RULES = [
    { expr: "wave", patterns: [/こんにちは|おはよう|こんばんは|やあ|はじめまして|ようこそ|hello|hi\b/i] },
    { expr: "cheer", patterns: [/がんば|頑張|できた|すごい|ナイス|よくでき|おめでと|合格|クリア|すばらし|いいね|えらい|拍手/i] },
    { expr: "sad", patterns: [/つらい|悲し|残念|ごめん|申し訳|しんどい|不安|心配/i] },
    { expr: "think", patterns: [/どうして|なぜ|考え|教えて|どうすれば|？|\?/] },
    { expr: "surprised", patterns: [/えっ|まじ|びっくり|本当に|！？|驚/i] },
    { expr: "happy", patterns: [/ありがと|嬉し|楽し|うれし|笑|ワクワク|やった/i] },
  ];

  function mapEmotion(name) {
    const k = String(name || "").toLowerCase();
    return EMOTION_MAP[k] || (EXPRESSIONS[k] ? k : "neutral");
  }

  function detectExpression(text, opts = {}) {
    const t = String(text || "");
    const tag = t.match(/^\[(neutral|joy|happy|sadness|sad|surprise|surprised|think|cheer|wave)\]/i);
    if (tag) return mapEmotion(tag[1]);
    if (opts.emotion) return mapEmotion(opts.emotion);
    if (opts.greeting) return "wave";
    for (const rule of SITUATION_RULES) {
      if (rule.patterns.some((re) => re.test(t))) return rule.expr;
    }
    return opts.fallback || "neutral";
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
        "luna-idle", "luna-bob", "luna-wave-motion", "luna-cheer-motion",
        "luna-talk-motion", "luna-tap-bounce"
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
      if (this.current === "wave") this._setMotionClass("luna-wave-motion");
      else if (this.current === "cheer") this._setMotionClass("luna-cheer-motion");
      else if (this.current === "talk") this._setMotionClass("luna-talk-motion");
      else if (!this.speaking) this._setMotionClass("luna-idle");

      if (this.exprTimer) {
        clearTimeout(this.exprTimer);
        this.exprTimer = null;
      }
      if (holdMs > 0) {
        this.exprTimer = setTimeout(() => {
          if (!this.speaking) this.setExpression("neutral");
        }, holdMs);
      }
      return this.current;
    }

    playExpression(name, holdMs = 2200) {
      if (this.speaking && name !== "talk" && name !== "blink") return;
      this.setExpression(name, holdMs);
    }

    /** Apply emotion from API game_state.emotion or dialogue tags */
    applyEmotion(emotion, holdMs = 2400) {
      const key = mapEmotion(emotion);
      this.playExpression(key, holdMs);
      return key;
    }

    reactToText(text, opts = {}) {
      const expr = detectExpression(text, opts);
      const hold = expr === "wave" ? 2800 : expr === "cheer" ? 2600 : 2200;
      this.playExpression(expr, hold);
      return expr;
    }

    /** tapMotions equivalent */
    tap() {
      if (this.speaking) return;
      const pick = TAP_MOTIONS[Math.floor(Math.random() * TAP_MOTIONS.length)];
      this._setMotionClass("luna-tap-bounce");
      this.playExpression(pick, 2000);
    }

    startIdle() {
      this.stopIdle();
      this._setMotionClass("luna-idle");
      // occasional soft bob pulse
      this.idleTimer = setInterval(() => {
        if (this.speaking || !this.stage) return;
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
          if (!this.speaking && (this.current === "neutral" || this.current === "happy")) {
            const prev = this.current;
            this.setExpression("blink");
            setTimeout(() => {
              if (!this.speaking && this.current === "blink") this.setExpression(prev === "happy" ? "happy" : "neutral");
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
      this.setExpression("neutral");
      this._setMotionClass("luna-idle");
    }

    destroy() {
      this.stopBlink();
      this.stopLipSync();
      this.stopIdle();
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
