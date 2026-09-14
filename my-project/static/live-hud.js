/**
 * Live HUD — companion flies beside the RPG hero and reports what it sees.
 * In-app only (scroll, pointer, typing, tab). Does not capture the OS screen.
 */
(function (global) {
  "use strict";

  const IDLE_MS = 20000;
  const AFK_MS = 8000;
  const REST_MS = 18 * 60 * 1000;
  let root, sprite, bubble, watchNow, watchLog;
  let lastInput = Date.now();
  let hiddenAt = 0;
  let studyOpenedAt = 0;
  let speakingUntil = 0;
  let lastEvent = "";
  let restWarned = false;
  let raf = 0;
  let x = 0;
  let y = 0;
  let tx = 0;
  let ty = 0;
  let ptrX = 0;
  let ptrY = 0;
  let ptrMix = 0;
  let logs = [];
  let lastWatchKey = "";
  let lastMissSpeak = 0;
  let lastCheerAt = 0;

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

  function setWatch(key, text) {
    if (!watchNow) return;
    if (key === lastWatchKey) return;
    lastWatchKey = key;
    watchNow.textContent = text;
    logs.unshift(text);
    logs = logs.slice(0, 5);
    if (watchLog) {
      watchLog.innerHTML = logs.map((t) => "<li>" + t + "</li>").join("");
    }
    root && root.setAttribute("data-see", key);
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
      say(res.line_ja, res.emotion, event === "suspect" ? 5000 : 2800);
    } catch (_) {
      const fallback = {
        suspect: "今、逃げた？戻ってきたなら続き。",
        cheer: "その打ち込み、届いてる。",
        win: "よくやった。",
        rest: "一度、目を休めて。",
        idle: "手が止まってる。一行でいい。",
        lose: "負けても、進捗は残ってる。",
        follow: "見てるよ。ついてく。",
      };
      say(
        fallback[event] || fallback.follow,
        event === "lose" || event === "rest" ? "sad" : event === "cheer" || event === "win" ? "cheer" : "think"
      );
    }
  }

  function markInput(kind) {
    lastInput = Date.now();
    if (root && root.classList.contains("idle")) root.classList.remove("idle");
    if (kind === "type") setWatch("type", "入力を読んでいる");
    else if (kind === "scroll") setWatch("scroll", "画面の動きを見ている");
    else if (kind === "pointer") setWatch("pointer", "カーソルを追っている");
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
    if (now - lastInput > IDLE_MS) {
      root.classList.add("idle");
      setWatch("idle", studying ? "解答が止まっている" : "動きがない");
      if (lastEvent !== "idle") emit("idle");
    }
    if (studying && studyOpenedAt && now - studyOpenedAt > REST_MS && !restWarned) {
      restWarned = true;
      emit("rest");
      setWatch("rest", "長く戦っている → 休憩を勧めた");
    }
  }

  function onVis() {
    if (document.visibilityState === "hidden") {
      hiddenAt = Date.now();
      setWatch("away", "画面から消えた（タブを隠した）");
      return;
    }
    if (hiddenAt && Date.now() - hiddenAt > AFK_MS) {
      emit("suspect");
      root && root.classList.add("suspect");
      setWatch("suspect", "戻ってきた。疑っている");
      setTimeout(() => root && root.classList.remove("suspect"), 4000);
    } else if (hiddenAt) {
      setWatch("back", "画面に戻った");
    }
    hiddenAt = 0;
    lastInput = Date.now();
  }

  function heroAnchor() {
    const studyOpen = document.querySelector(".study-modal.open");
    const examOpen = document.querySelector(".exam-modal.open");
    const fighter = (examOpen || studyOpen) && (examOpen || studyOpen).querySelector(".js-player-img");
    if (fighter && fighter.getBoundingClientRect().width) {
      const r = fighter.getBoundingClientRect();
      return { x: r.right - 8, y: r.top - 28 };
    }
    const mapSec = document.getElementById("fsq-map");
    const av = document.getElementById("mapAvatar");
    if (mapSec && mapSec.classList.contains("active") && av && !av.hidden) {
      const r = av.getBoundingClientRect();
      return { x: r.right + 6, y: r.top - 18 };
    }
    const doll = document.querySelector("#rpgDollMount img.doll-sprite") || document.getElementById("rpgDollMount");
    if (doll) {
      const r = doll.getBoundingClientRect();
      if (r.width > 8) return { x: r.right - 4, y: r.top + 8 };
    }
    return { x: window.innerWidth - 108, y: window.innerHeight - 200 };
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    if (!root || root.hidden) return;
    const a = heroAnchor();
    if (ptrMix > 0.04) {
      tx = a.x * 0.42 + (ptrX - 36) * 0.58;
      ty = a.y * 0.42 + (ptrY - 42) * 0.58;
      ptrMix *= 0.9;
    } else {
      tx = a.x;
      ty = a.y;
    }
    x += (tx - x) * 0.16;
    y += (ty - y) * 0.16;
    const maxX = window.innerWidth - 92;
    const maxY = window.innerHeight - 120;
    x = Math.max(8, Math.min(maxX, x));
    y = Math.max(8, Math.min(maxY, y));
    root.style.transform = "translate(" + Math.round(x) + "px," + Math.round(y) + "px)";
  }

  function show() {
    if (!root) return;
    root.hidden = false;
    setFace("happy");
    const a = heroAnchor();
    x = a.x;
    y = a.y;
    tx = x;
    ty = y;
    setWatch("follow", "冒険者のそばについている");
    emit("follow");
    if (!raf) loop();
  }

  function hide() {
    if (!root) return;
    root.hidden = true;
  }

  function enterStudy() {
    studyOpenedAt = Date.now();
    restWarned = false;
    lastInput = Date.now();
    setWatch("study", "解答を読んでいる。用語が攻撃になる");
    emit("cheer");
  }

  function leaveStudy() {
    studyOpenedAt = 0;
    root && root.classList.remove("idle", "suspect");
    setWatch("follow", "拠点に戻った");
  }

  function noteHit(term) {
    setWatch("hit", term ? "用語「" + term + "」を見つけた → 攻撃" : "正しい内容が届いた");
    const now = Date.now();
    if (now - lastCheerAt > 4000) {
      lastCheerAt = now;
      emit("cheer");
    }
  }

  function noteMiss() {
    const now = Date.now();
    if (now - lastMissSpeak < 2500) return;
    lastMissSpeak = now;
    setWatch("miss", "まだ用語が足りない。攻撃にならない");
  }

  function bind() {
    root = document.getElementById("liveHud");
    sprite = document.getElementById("liveHudSprite");
    bubble = document.getElementById("liveHudBubble");
    watchNow = document.getElementById("liveWatchNow");
    watchLog = document.getElementById("liveWatchLog");
    if (!root) return;
    document.addEventListener("visibilitychange", onVis);
    document.addEventListener(
      "pointermove",
      (e) => {
        if (root.hidden) return;
        ptrX = e.clientX;
        ptrY = e.clientY;
        ptrMix = 1;
        markInput("pointer");
      },
      { passive: true }
    );
    document.addEventListener(
      "scroll",
      () => {
        if (root.hidden) return;
        markInput("scroll");
      },
      { passive: true, capture: true }
    );
    document.addEventListener(
      "keydown",
      () => {
        if (root.hidden) return;
        markInput("type");
      },
      { passive: true }
    );
    setInterval(tick, 1200);
    setFace("happy");
    if (!raf) loop();
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
    setWatch: setWatch,
  };
})(window);
