/**
 * Live HUD — tiny companion that follows the user *inside* LUNA/FSQ.
 * Watches in-app presence only (tab, typing, idle). Does not capture the OS screen.
 */
(function (global) {
  "use strict";

  const IDLE_MS = 45000;
  const AFK_MS = 22000;
  const REST_MS = 22 * 60 * 1000;
  let root, sprite, bubble;
  let lastInput = Date.now();
  let hiddenAt = 0;
  let studyOpenedAt = 0;
  let speakingUntil = 0;
  let lastEvent = "";
  let restWarned = false;

  function row() {
    return (global.companionByIdPublic && global.companionByIdPublic()) || {};
  }

  function exprUrl(name) {
    const r = row();
    const prefix = r.prefix || r.id || "luna";
    const base = String(r.base || "/static/live2d/" + prefix + "-expressions").replace(/\/$/, "");
    return base + "/" + prefix + "-" + name + ".png";
  }

  function setFace(emotion) {
    if (!sprite) return;
    const map = { sad: "sad", think: "think", cheer: "cheer", happy: "happy", surprised: "surprised", wave: "wave" };
    sprite.src = exprUrl(map[emotion] || "happy");
  }

  function say(text, emotion, ms) {
    if (!bubble) return;
    bubble.hidden = false;
    bubble.textContent = text || "";
    setFace(emotion || "happy");
    speakingUntil = Date.now() + (ms || 3200);
    root && root.classList.add("speaking");
  }

  async function emit(event, extra) {
    if (event === lastEvent && event === "follow") return;
    lastEvent = event;
    root && root.setAttribute("data-hud", event);
    try {
      const q = "/companion/presence?event=" + encodeURIComponent(event) + (extra ? "&extra=" + encodeURIComponent(extra) : "");
      const res = await (global.lunaApi ? global.lunaApi(q) : fetch(q, { credentials: "same-origin" }).then((r) => r.json()));
      say(res.line_ja, res.emotion, event === "suspect" ? 5000 : 2800);
    } catch (_) {
      const fallback = {
        suspect: "今、逃げた？",
        cheer: "その打ち込み、届いてる。",
        win: "よくやった。",
        rest: "一度、目を休めて。",
        idle: "手が止まってる。一行でいい。",
        lose: "負けても、進捗は残ってる。",
        follow: "見てるよ。",
      };
      say(fallback[event] || fallback.follow, event === "lose" || event === "rest" ? "sad" : event === "cheer" || event === "win" ? "cheer" : "think");
    }
    if (global.luna && global.luna.applyEmotion) {
      try {
        global.luna.applyEmotion(event === "win" || event === "cheer" ? "cheer" : event === "lose" ? "sad" : "think", 1200);
      } catch (_) {}
    }
  }

  function markInput() {
    lastInput = Date.now();
    if (root && root.classList.contains("idle")) root.classList.remove("idle");
  }

  function tick() {
    if (!root || root.hidden) return;
    const now = Date.now();
    if (now > speakingUntil && bubble && !bubble.hidden) {
      bubble.hidden = true;
      root.classList.remove("speaking");
      setFace("happy");
    }
    const studying = !!(document.querySelector(".study-modal.open") || document.querySelector(".exam-modal.open"));
    if (studying && now - lastInput > IDLE_MS) {
      root.classList.add("idle");
      if (lastEvent !== "idle") emit("idle");
    }
    if (studying && studyOpenedAt && now - studyOpenedAt > REST_MS && !restWarned) {
      restWarned = true;
      emit("rest");
    }
  }

  function onVis() {
    if (document.visibilityState === "hidden") {
      hiddenAt = Date.now();
      return;
    }
    const studying = !!(document.querySelector(".study-modal.open") || document.querySelector(".exam-modal.open"));
    if (studying && hiddenAt && Date.now() - hiddenAt > AFK_MS) {
      emit("suspect");
      root && root.classList.add("suspect");
      setTimeout(() => root && root.classList.remove("suspect"), 4000);
    }
    hiddenAt = 0;
    markInput();
  }

  function show() {
    if (!root) return;
    root.hidden = false;
    setFace("happy");
    emit("follow");
  }

  function hide() {
    if (!root) return;
    root.hidden = true;
  }

  function enterStudy() {
    studyOpenedAt = Date.now();
    restWarned = false;
    markInput();
    root && root.classList.add("in-battle");
    emit("cheer");
  }

  function leaveStudy() {
    studyOpenedAt = 0;
    root && root.classList.remove("in-battle", "idle", "suspect");
  }

  function bind() {
    root = document.getElementById("liveHud");
    sprite = document.getElementById("liveHudSprite");
    bubble = document.getElementById("liveHudBubble");
    if (!root) return;
    document.addEventListener("visibilitychange", onVis);
    ["keydown", "pointerdown", "input"].forEach((ev) => {
      document.addEventListener(ev, markInput, { passive: true });
    });
    setInterval(tick, 2500);
    setFace("happy");
  }

  global.LiveHud = {
    bind: bind,
    show: show,
    hide: hide,
    emit: emit,
    enterStudy: enterStudy,
    leaveStudy: leaveStudy,
    exprUrl: exprUrl,
    say: say,
  };
})(window);
