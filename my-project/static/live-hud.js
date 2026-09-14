/**
 * Live HUD — companion stands in a corner and watches the user's work.
 * Faces inward toward the sheet. In-app only; does not capture the OS screen.
 */
(function (global) {
  "use strict";

  const IDLE_MS = 20000;
  const AFK_MS = 8000;
  const REST_MS = 18 * 60 * 1000;
  let root, sprite, bubble, homeParent;
  let lastInput = Date.now();
  let hiddenAt = 0;
  let studyOpenedAt = 0;
  let speakingUntil = 0;
  let lastEvent = "";
  let restWarned = false;
  let lastCheerAt = 0;
  let lastMissSpeak = 0;

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
    sprite.src = exprUrl(map[emotion] || "think");
  }

  function studying() {
    return !!(document.querySelector(".study-modal.open") || document.querySelector(".exam-modal.open"));
  }

  function dockHost() {
    return (
      document.querySelector(".study-modal.open .study-battle-arena") ||
      document.querySelector(".exam-modal.open .study-battle-arena")
    );
  }

  function park() {
    if (!root) return;
    root.style.left = "";
    root.style.top = "";
    root.style.bottom = "";
    root.style.right = "";
    root.style.transform = "none";
    root.classList.add("inward");
    const host = dockHost();
    if (studying() && host) {
      if (root.parentElement !== host) host.appendChild(root);
      root.classList.add("sheet-docked", "study-watch");
    } else {
      if (homeParent && root.parentElement !== homeParent) homeParent.appendChild(root);
      root.classList.remove("sheet-docked", "study-watch");
    }
  }

  function say(text, emotion, ms) {
    if (!bubble) return;
    bubble.hidden = false;
    bubble.textContent = text || "";
    setFace(emotion || "think");
    speakingUntil = Date.now() + (ms || 2800);
    root && root.classList.add("speaking");
  }

  async function emit(event, extra) {
    lastEvent = event;
    root && root.setAttribute("data-hud", event);
    try {
      const q =
        "/companion/presence?event=" +
        encodeURIComponent(event) +
        (extra ? "&extra=" + encodeURIComponent(extra) : "");
      const res = await (global.lunaApi
        ? global.lunaApi(q)
        : fetch(q, { credentials: "same-origin" }).then((r) => r.json()));
      say(res.line_ja, res.emotion, event === "suspect" ? 5000 : 2600);
    } catch (_) {
      const fallback = {
        suspect: "今、逃げた？戻ってきたなら続き。",
        cheer: "その打ち込み、届いてる。",
        win: "よくやった。",
        rest: "一度、目を休めて。",
        idle: "手が止まってる。一行でいい。",
        lose: "負けても、進捗は残ってる。",
        follow: "見てるよ。その画面。",
      };
      say(
        fallback[event] || fallback.follow,
        event === "lose" || event === "rest" ? "sad" : event === "cheer" || event === "win" ? "cheer" : "think"
      );
    }
  }

  function tick() {
    if (!root || root.hidden) return;
    park();
    const now = Date.now();
    if (now > speakingUntil && bubble && !bubble.hidden) {
      bubble.hidden = true;
      root.classList.remove("speaking");
      setFace(studying() ? "think" : "happy");
    }
    if (now - lastInput > IDLE_MS) {
      root.classList.add("idle");
      if (lastEvent !== "idle") emit("idle");
    }
    if (studying() && studyOpenedAt && now - studyOpenedAt > REST_MS && !restWarned) {
      restWarned = true;
      emit("rest");
    }
  }

  function onVis() {
    if (document.visibilityState === "hidden") {
      hiddenAt = Date.now();
      return;
    }
    if (hiddenAt && Date.now() - hiddenAt > AFK_MS) {
      emit("suspect");
      root && root.classList.add("suspect");
      setTimeout(() => root && root.classList.remove("suspect"), 4000);
    }
    hiddenAt = 0;
    lastInput = Date.now();
  }

  function show() {
    if (!root) return;
    root.hidden = false;
    setFace("think");
    park();
    emit("follow");
  }

  function hide() {
    if (!root) return;
    root.hidden = true;
  }

  function enterStudy() {
    studyOpenedAt = Date.now();
    restWarned = false;
    lastInput = Date.now();
    park();
    setFace("think");
    emit("cheer");
  }

  function leaveStudy() {
    studyOpenedAt = 0;
    if (root) {
      root.classList.remove("idle", "suspect", "study-watch", "sheet-docked");
      if (homeParent && root.parentElement !== homeParent) homeParent.appendChild(root);
    }
    setFace("happy");
  }

  function noteHit(term) {
    setFace("cheer");
    const now = Date.now();
    if (now - lastCheerAt > 4000) {
      lastCheerAt = now;
      emit("cheer", term || "");
    }
  }

  function noteMiss() {
    const now = Date.now();
    if (now - lastMissSpeak < 2800) return;
    lastMissSpeak = now;
    setFace("think");
  }

  function bind() {
    root = document.getElementById("liveHud");
    sprite = document.getElementById("liveHudSprite");
    bubble = document.getElementById("liveHudBubble");
    if (!root) return;
    homeParent = root.parentElement;
    document.addEventListener("visibilitychange", onVis);
    document.addEventListener(
      "keydown",
      () => {
        if (root.hidden) return;
        lastInput = Date.now();
        root.classList.remove("idle");
        if (studying()) setFace("think");
      },
      { passive: true }
    );
    window.addEventListener("resize", park);
    setInterval(tick, 1200);
    setFace("think");
    park();
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
    noteHit: noteHit,
    noteMiss: noteMiss,
    setWatch: function () {},
  };
})(window);
