(function () {
  "use strict";

  const REGION_LORE = [
    {
      title: "始まりの平原",
      chapter: "CHAPTER I",
      lore: "見習い冒険者が最初に踏む大地。基礎を学び、最初のクエストに挑む安全なキャンプ地。",
      tip: "ここで身につけた基礎が、後のボス戦を支える。",
      monster: "スライム課題",
      biome: "plains",
    },
    {
      title: "知恵の森",
      chapter: "CHAPTER II",
      lore: "古いコードの残響が木々の間を漂う。論理と構造を学ぶ者だけが奥へ進める試練の森。",
      tip: "詰まったらガイドを開く — 森の精霊（定石）が道を示す。",
      monster: "バグウルフ",
      biome: "forest",
    },
    {
      title: "試練の丘陵",
      chapter: "CHAPTER III",
      lore: "実践課題が連なる起伏の地。書いて、直して、提出する繰り返しが力になる。",
      tip: "Paiza風の課題は「モンスター」。解答コードが武器になる。",
      monster: "アルゴリズムゴーレム",
      biome: "hills",
    },
    {
      title: "雲上の城",
      chapter: "CHAPTER IV",
      lore: "週次・月次の試験が待ち受ける高城。ここまで来た者だけが門を叩ける。",
      tip: "ボスに負けても進捗は消えない — 何度でも挑戦できる。",
      monster: "試験の番人",
      biome: "castle",
    },
    {
      title: "終焉の扉",
      chapter: "FINAL",
      lore: "最終形態への扉。スキル・実績・作品が鍵となる、キャリアのゴール地点。",
      tip: "冒険録を育てれば、就活の自己PRにもなる。",
      monster: "キャリアドラゴン",
      biome: "gate",
    },
  ];

  const NARRATOR_IDLE = [
    "風がクエストボードを揺らしている… 今日も一歩、未来へ進もう。",
    "装備を整え、スキルツリーを確認。準備は冒険の半分だ。",
    "学びは経験値。提出は攻撃。ガイドは魔法のヒント。",
    "マップの先に光が見える。進めば進むほど、未来の自分が近づく。",
  ];

  let lastLevel = null;
  let mapDepartHandler = null;
  let lastToastAt = 0;
  let lastHitAt = 0;
  let lastPlayerAct = 0;
  let lastMissAt = 0;
  let combatTimer = 0;
  let clockTimer = 0;
  let battlePct = 12;
  let typingCombo = 0;
  let travelAnimating = false;
  let questLimitMsVal = 6 * 60 * 1000;
  let questStartedAt = 0;
  let timedOut = false;
  let combatTurn = 0;
  let timeUpHandler = null;
  let fightBlank = true;
  let fightArmed = false;

  function $(id) {
    return document.getElementById(id);
  }

  /* ===== SFX (Web Audio — light juice) ===== */
  const Sfx = {
    ctx: null,
    ensure() {
      try {
        if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        if (this.ctx.state === "suspended") this.ctx.resume();
      } catch (_) {}
      return this.ctx;
    },
    play(freq, dur, type, vol) {
      try {
        const ctx = this.ensure();
        if (!ctx) return;
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = type || "sine";
        o.frequency.value = freq;
        g.gain.value = vol == null ? 0.03 : vol;
        o.connect(g);
        g.connect(ctx.destination);
        o.start();
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
        o.stop(ctx.currentTime + dur);
      } catch (_) {}
    },
    portal() {
      this.play(196, 0.35, "triangle", 0.04);
      setTimeout(() => this.play(294, 0.25, "triangle", 0.035), 120);
      setTimeout(() => this.play(392, 0.4, "sine", 0.04), 240);
    },
    questStart() {
      this.play(440, 0.08);
      setTimeout(() => this.play(554, 0.1), 60);
      setTimeout(() => this.play(659, 0.16), 130);
    },
    questClear() {
      this.play(523, 0.08);
      setTimeout(() => this.play(659, 0.08), 80);
      setTimeout(() => this.play(784, 0.1), 160);
      setTimeout(() => this.play(1047, 0.28), 250);
    },
    levelUp() {
      this.play(330, 0.1);
      setTimeout(() => this.play(440, 0.1), 90);
      setTimeout(() => this.play(554, 0.1), 180);
      setTimeout(() => this.play(880, 0.32), 280);
    },
    hit() {
      this.play(180 + Math.random() * 40, 0.05, "square", 0.018);
    },
    click() {
      this.play(720, 0.04, "triangle", 0.02);
    },
    boss() {
      this.play(110, 0.4, "sawtooth", 0.03);
      setTimeout(() => this.play(98, 0.5, "sawtooth", 0.025), 200);
      setTimeout(() => this.play(220, 0.2, "triangle", 0.03), 500);
    },
    toast() {
      this.play(880, 0.06, "sine", 0.02);
    },
  };

  /* ===== DOM helpers ===== */
  function ensureLayer(id, className, parent) {
    let el = $(id);
    if (el) return el;
    el = document.createElement("div");
    el.id = id;
    el.className = className;
    el.setAttribute("aria-hidden", "true");
    (parent || document.body).appendChild(el);
    return el;
  }

  function initLayers() {
    const root = $("tab-fsq") || document.body;
    ensureLayer("worldToastStack", "world-toast-stack", root);
    ensureLayer("worldFlash", "world-flash", document.body);
    ensureLayer("worldConfetti", "world-confetti", document.body);
    ensureLayer("regionTitleCard", "region-title-card", document.body);
    ensureLayer("bossIntro", "boss-intro", document.body);
    const title = $("regionTitleCard");
    if (title && !title.innerHTML) {
      title.innerHTML =
        '<div class="rtc-inner"><p class="rtc-ch" id="rtcChapter">CHAPTER</p><h3 id="rtcTitle">—</h3><p id="rtcSub">—</p></div>';
    }
    const boss = $("bossIntro");
    if (boss && !boss.innerHTML) {
      boss.innerHTML =
        '<div class="bi-vignette"></div><div class="bi-inner">' +
        '<p class="bi-warn">⚠ BOSS APPEARS</p>' +
        '<div class="bi-face" id="biFace"><img id="biFaceImg" alt=""></div>' +
        '<h3 id="biName">試験の番人</h3>' +
        '<p id="biHint">これまでの学習が武器になる</p>' +
        '<button type="button" id="biFightBtn">⚔ 戦闘開始</button></div>';
    }
  }

  function initAmbient() {
    initLayers();
    const box = $("worldAmbient");
    if (!box || box.dataset.ready) return;
    box.dataset.ready = "1";
    box.innerHTML = "";
    for (let i = 0; i < 36; i++) {
      const p = document.createElement("span");
      p.className = "wp " + (i % 3 === 0 ? "gold" : i % 3 === 1 ? "teal" : "soft");
      p.style.left = Math.random() * 100 + "%";
      p.style.top = Math.random() * 100 + "%";
      p.style.animationDelay = Math.random() * 6 + "s";
      p.style.animationDuration = 4 + Math.random() * 5 + "s";
      box.appendChild(p);
    }
  }

  function flash(kind) {
    const el = $("worldFlash");
    if (!el) return;
    el.className = "world-flash " + (kind || "gold") + " go";
    setTimeout(() => el.classList.remove("go"), 420);
  }

  function toast(msg, kind) {
    const now = Date.now();
    if (now - lastToastAt < 350) return;
    lastToastAt = now;
    const stack = $("worldToastStack");
    if (!stack) return;
    const t = document.createElement("div");
    t.className = "world-toast " + (kind || "");
    t.textContent = msg;
    stack.appendChild(t);
    Sfx.toast();
    setTimeout(() => t.classList.add("show"), 10);
    setTimeout(() => {
      t.classList.remove("show");
      setTimeout(() => t.remove(), 280);
    }, 2200);
  }

  function confetti(n) {
    const box = $("worldConfetti");
    if (!box) return;
    box.innerHTML = "";
    const count = n || 28;
    for (let i = 0; i < count; i++) {
      const p = document.createElement("i");
      p.style.left = Math.random() * 100 + "%";
      p.style.animationDelay = Math.random() * 0.4 + "s";
      p.style.background = ["#ffd27a", "#5ecfc0", "#ff7a7a", "#fff", "#b47aff"][i % 5];
      box.appendChild(p);
    }
    box.classList.add("go");
    setTimeout(() => {
      box.classList.remove("go");
      box.innerHTML = "";
    }, 1800);
  }

  function showPortal() {
    const el = $("worldPortal");
    if (!el) return;
    if (sessionStorage.getItem("fsq_portal_seen")) return;
    sessionStorage.setItem("fsq_portal_seen", "1");
    el.classList.add("open");
    Sfx.portal();
    flash("teal");
    setTimeout(() => el.classList.remove("open"), 2400);
  }

  function showRegionTitle(index, force) {
    const lore = REGION_LORE[index] || REGION_LORE[0];
    const key = "fsq_region_title_" + index;
    if (!force && sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    const card = $("regionTitleCard");
    if (!card) return;
    const ch = $("rtcChapter");
    const ti = $("rtcTitle");
    const sub = $("rtcSub");
    if (ch) ch.textContent = lore.chapter;
    if (ti) ti.textContent = lore.title;
    if (sub) sub.textContent = lore.tip;
    card.classList.add("open");
    Sfx.click();
    setTimeout(() => card.classList.remove("open"), 2600);
  }

  function expPct(status, expProgressFn) {
    const lv = status.level || 1;
    const exp = status.total_exp || 0;
    if (typeof expProgressFn === "function") return expProgressFn(exp, lv).pct;
    return Math.min(100, Math.round(((exp % 100) / 100) * 100));
  }

  function currentRegionIdx(map) {
    const list = (map && map.stages) || [];
    const i = list.findIndex((s) => s.current);
    return i >= 0 ? i : 0;
  }

  function currentRegionName(map) {
    const list = (map && map.stages) || [];
    const cur = list.find((s) => s.current) || list[0];
    return cur ? cur.label_ja || cur.id : "始まりの平原";
  }

  function renderHud(status, map, expProgressFn) {
    const hud = $("worldHud");
    if (!hud) return;
    hud.hidden = !status.selected;
    if (!status.selected) return;
    const lv = $("whLv");
    if (lv) lv.textContent = "Lv." + (status.level || 1);
    const bar = $("whExpBar");
    if (bar) bar.style.width = expPct(status, expProgressFn) + "%";
    const reg = $("whRegion");
    if (reg) reg.textContent = currentRegionName(map);
    const quest = $("whQuest");
    if (quest) {
      const n = status.next_lesson;
      quest.textContent = n ? "⚔ " + (n.title_ja || n.id) : "クエスト探索中…";
    }
    const power = $("whPower");
    if (power) power.textContent = "PWR " + expPct(status, expProgressFn) + "%";
  }

  function renderNarrator(status, map) {
    const box = $("worldNarrator");
    if (!box) return;
    box.classList.remove("expanded");
    if (!box.dataset.toggleBound) {
      box.dataset.toggleBound = "1";
      box.addEventListener("click", () => box.classList.toggle("expanded"));
    }
    if (!status.selected) {
      box.innerHTML =
        '<div class="wn-inner"><span class="wn-icon">🌙</span><div><strong>冒険の大陸が目を覚ます</strong><p>クラスと進路を選ぶと、ここがあなただけのクエスト世界になる。</p></div></div>';
      return;
    }
    const weekly = status.weekly_story;
    if (weekly && weekly.story_ja) {
      const hl = (weekly.highlights || []).slice(0, 2).join(" ・ ");
      box.innerHTML =
        '<div class="wn-inner"><span class="wn-icon">📖</span><div><strong>今週の物語（' +
        (weekly.week_label || "") +
        "）</strong><p>" +
        weekly.story_ja +
        '</p><em class="wn-tip">' +
        (weekly.tip_ja || "学びは経験値。一歩ずつ未来へ。") +
        (hl ? " — " + hl : "") +
        "</em></div></div>";
      return;
    }
    const idx = currentRegionIdx(map);
    const lore = REGION_LORE[idx] || REGION_LORE[0];
    const next = status.next_lesson;
    const tail = next
      ? "次のクエスト「" + (next.title_ja || next.id) + "」がボードに掲示されている。"
      : NARRATOR_IDLE[Math.floor(Date.now() / 60000) % NARRATOR_IDLE.length];
    box.innerHTML =
      '<div class="wn-inner"><span class="wn-icon">📜</span><div><strong>' +
      lore.chapter +
      " — " +
      lore.title +
      "</strong><p>" +
      lore.lore +
      " " +
      tail +
      '</p><em class="wn-tip">' +
      lore.tip +
      "</em></div></div>";
  }

  function checkLevelUp(level) {
    if (lastLevel == null) {
      lastLevel = level;
      return;
    }
    if (level > lastLevel) {
      const ov = $("levelUpOverlay");
      const lvEl = $("luLevel");
      const msg = $("luMsg");
      if (lvEl) lvEl.textContent = "Lv." + level;
      if (msg) msg.textContent = "新しい力が目覚めた — スキルと装備が強化される";
      if (ov) {
        ov.classList.add("open");
        Sfx.levelUp();
        flash("gold");
        confetti(36);
        toast("LEVEL UP! Lv." + level, "gold");
        setTimeout(() => ov.classList.remove("open"), 3000);
      }
    }
    lastLevel = level;
  }

  function renderMapPanel(stage, index, journeyStatus) {
    const panel = $("mapRegionPanel");
    if (!panel) return;
    const lore = REGION_LORE[index] || REGION_LORE[0];
    const icons = ["⛺", "🌲", "⛰", "🏰", "👑"];
    if ($("mrpIcon")) $("mrpIcon").textContent = icons[index] || "◆";
    if ($("mrpTitle")) $("mrpTitle").textContent = stage.label_ja || lore.title;
    if ($("mrpSub")) {
      $("mrpSub").textContent = stage.current
        ? "★ 現在地 ・ " + lore.chapter
        : stage.cleared
          ? "クリア済"
          : stage.unlocked
            ? "探索可能"
            : "未開放";
    }
    if ($("mrpLore")) $("mrpLore").textContent = lore.lore + " " + lore.tip;
    const btn = $("mrpDepartBtn");
    if (btn) {
      const les = journeyStatus.next_lesson || null;
      const canGo = stage.current && les && les.available && !les.completed;
      btn.disabled = !canGo;
      btn.textContent = canGo
        ? "⚔ 「" + (les.title_ja || les.id) + "」に出撃"
        : !stage.unlocked
          ? "🔒 前のエリアをクリアしよう"
          : stage.current
            ? "このエリアのクエストを確認"
            : "別のエリアを選択中";
      btn.onclick = () => {
        if (canGo && mapDepartHandler) {
          Sfx.questStart();
          toast("出撃！ " + (les.title_ja || ""), "teal");
          mapDepartHandler(les.id);
        }
      };
    }
    panel.classList.add("open");
    if (stage.current) showRegionTitle(index, false);
  }

  function animateMapTravel(fromPos, toPos, onDone) {
    const av = $("mapAvatar");
    if (!av || !toPos || travelAnimating) {
      if (onDone) onDone();
      return;
    }
    travelAnimating = true;
    av.classList.add("traveling");
    if (fromPos) {
      av.style.left = fromPos.left;
      av.style.top = fromPos.top;
    }
    void av.offsetWidth;
    av.style.transition = "left .9s cubic-bezier(.2,.8,.2,1), top .9s cubic-bezier(.2,.8,.2,1)";
    av.style.left = toPos.left;
    av.style.top = toPos.top;
    const strip = document.querySelector(".map-strip");
    if (strip) {
      const pulse = document.createElement("span");
      pulse.className = "map-travel-pulse";
      pulse.style.left = toPos.left;
      pulse.style.top = toPos.top;
      strip.appendChild(pulse);
      pulse.addEventListener("animationend", () => pulse.remove());
    }
    Sfx.click();
    setTimeout(() => {
      av.classList.remove("traveling");
      av.style.transition = "";
      travelAnimating = false;
      if (onDone) onDone();
    }, 950);
  }

  const BOSS_ART = {
    lesson: "/static/rpg/bosses/quest-slime.png",
    weekly: "/static/rpg/bosses/boss-weekly.png",
    monthly: "/static/rpg/bosses/boss-monthly.png",
    career_final: "/static/rpg/bosses/boss-final.png",
  };

  function heroSprite() {
    if (window.FsqHeroSprite) return window.FsqHeroSprite;
    if (window.CharacterDoll && CharacterDoll.chibiPath) {
      return CharacterDoll.chibiPath(window.FsqHeroClass || "swordsman", window.FsqHeroRank || "novice");
    }
    return "/static/rpg/chibi/swordsman_novice.png";
  }

  function buddySprite(expr) {
    if (window.LiveHud && LiveHud.exprUrl) return LiveHud.exprUrl(expr || "cheer");
    return "/static/live2d/luna-expressions/luna-cheer.png";
  }

  function bossArt(kind) {
    return BOSS_ART[kind] || BOSS_ART.lesson;
  }

  function activeArena() {
    const exam = $("examModal");
    if (exam && exam.classList.contains("open")) return $("examBattleArena") || $("studyBattleArena");
    return $("studyBattleArena");
  }

  function paintFighters(kind, monsterName) {
    const arena = activeArena();
    if (!arena) return;
    arena.hidden = false;
    const pImg = arena.querySelector(".js-player-img") || $("battlePlayerImg");
    const bImg = arena.querySelector(".js-boss-img") || $("battleBossImg");
    const pName = arena.querySelector(".js-player-name");
    const bName = arena.querySelector(".js-boss-name") || $("battleMonsterName");
    if (pName) pName.textContent = window.FsqHeroName || "YOU";
    if (bName) bName.textContent = monsterName || "課題モンスター";
    const cls = window.FsqHeroClass || "swordsman";
    const heroWrap = arena.querySelector(".sba-side.player");
    const bossWrap = arena.querySelector(".sba-side.monster");
    if (heroWrap) {
      heroWrap.dataset.pack = cls;
      heroWrap.dataset.busy = "0";
      heroWrap.classList.remove("show-pose");
      ensurePoseLayer(heroWrap);
    }
    if (bossWrap) {
      bossWrap.dataset.pack = kind === "lesson" ? "slime" : "knight";
      bossWrap.dataset.busy = "0";
      bossWrap.classList.remove("show-pose");
      ensurePoseLayer(bossWrap);
    }
    if (pImg) {
      if (pImg.parentElement && !pImg.parentElement.classList.contains("sba-body")) {
        const wrap = document.createElement("div");
        wrap.className = "sba-body";
        pImg.parentElement.insertBefore(wrap, pImg);
        wrap.appendChild(pImg);
      }
      pImg.classList.add("idle-layer", "fighter-sprite");
      pImg.src = idleSrc(heroWrap, heroSprite());
      pImg.dataset.baseSrc = pImg.src;
    }
    if (bImg) {
      if (bImg.parentElement && !bImg.parentElement.classList.contains("sba-body")) {
        const wrap = document.createElement("div");
        wrap.className = "sba-body";
        bImg.parentElement.insertBefore(wrap, bImg);
        wrap.appendChild(bImg);
      }
      bImg.classList.add("idle-layer", "fighter-sprite");
      bImg.src = idleSrc(bossWrap, bossArt(kind || "lesson"));
      bImg.dataset.baseSrc = bImg.src;
    }
    arena.dataset.heroClass = cls;
    arena.dataset.bossKind = kind || "lesson";
    arena.classList.remove("hero-swordsman", "hero-mage", "hero-archer", "combo-hot", "mind-cast");
    arena.classList.add("hero-" + cls);
    const tension = arena.querySelector(".sba-tension") || $("battleTension");
    if (tension) {
      const line = {
        swordsman: "頭を使え。解答が剣になる。",
        mage: "頭を使え。解答が呪文になる。",
        archer: "頭を使え。解答が矢になる。",
      };
      tension.textContent = line[cls] || line.swordsman;
    }
    arena.classList.remove("ko-boss", "ko-player", "striking", "boss-striking", "clashing");
    arena.classList.add("fighting");
    const ko = arena.querySelector(".fs-ko");
    if (ko) ko.hidden = true;
    const combo = arena.querySelector(".sba-combo");
    if (combo) combo.hidden = true;
    if (bossWrap) bossWrap.classList.remove("ko");
    if (heroWrap) heroWrap.classList.remove("ko", "struggle");
    resetFighters(arena);
  }

  const FIGHT_POSES = {
    swordsman: {
      idle: "/static/rpg/fight/swordsman_idle.png?v=20260914t",
      atk: "/static/rpg/fight/swordsman_atk.png?v=20260914t",
      hit: "/static/rpg/fight/swordsman_hit.png?v=20260914t",
    },
    mage: {
      idle: "/static/rpg/fight/mage_idle.png?v=20260914t",
      atk: "/static/rpg/fight/mage_atk.png?v=20260914t",
    },
    archer: {
      idle: "/static/rpg/fight/archer_idle.png?v=20260914t",
      atk: "/static/rpg/fight/archer_atk.png?v=20260914t",
    },
    slime: {
      idle: "/static/rpg/fight/slime_idle.png?v=20260914t",
      atk: "/static/rpg/fight/slime_atk.png?v=20260914t",
      dodge: "/static/rpg/fight/slime_dodge.png?v=20260914t",
      hit: "/static/rpg/fight/slime_hit.png?v=20260914t",
    },
    knight: {
      atk: "/static/rpg/fight/knight_atk.png?v=20260914t",
    },
  };

  function poseUrl(side, pose) {
    const pack = (side && side.dataset.pack) || "";
    const map = FIGHT_POSES[pack];
    return map && map[pose];
  }

  function idleSrc(side, fallback) {
    return poseUrl(side, "idle") || fallback || "";
  }

  function ensurePoseLayer(side) {
    if (!side) return null;
    const body = side.querySelector(".sba-body");
    if (!body) return null;
    let idle = body.querySelector(".idle-layer") || body.querySelector(".js-player-img, .js-boss-img, .fighter-sprite");
    if (idle) idle.classList.add("idle-layer", "fighter-sprite");
    let layer = body.querySelector(".pose-layer");
    if (!layer) {
      layer = document.createElement("img");
      layer.className = "fighter-sprite pose-layer";
      layer.alt = "";
      layer.setAttribute("aria-hidden", "true");
      body.appendChild(layer);
    }
    return layer;
  }

  function sameSrc(img, url) {
    if (!img || !url) return false;
    try {
      const a = new URL(img.src, location.href);
      const b = new URL(url, location.href);
      return a.pathname === b.pathname && a.search === b.search;
    } catch (e) {
      return img.getAttribute("src") === url;
    }
  }

  function setPose(side, pose) {
    if (!side) return;
    const layer = ensurePoseLayer(side);
    if (!pose || pose === "base" || pose === "idle") {
      side.classList.remove("show-pose");
      return;
    }
    const url = poseUrl(side, pose);
    if (!url || !layer) {
      side.classList.remove("show-pose");
      return;
    }
    const show = () => side.classList.add("show-pose");
    if (sameSrc(layer, url) && layer.complete) {
      show();
      return;
    }
    layer.onload = show;
    layer.src = url;
    if (layer.complete) show();
  }

  function preloadFightPoses() {
    Object.keys(FIGHT_POSES).forEach((pack) => {
      Object.keys(FIGHT_POSES[pack]).forEach((pose) => {
        const im = new Image();
        im.src = FIGHT_POSES[pack][pose];
      });
    });
  }

  function startIdleLoop() {}

  function stopIdleLoop() {}

  const SKILL_NAME = {
    swordsman: ["一閃・龍牙", "斬撃・双牙", "剣技・天翔"],
    mage: ["雷鳴・天罰", "魔力弾・連", "術式・裂空"],
    archer: ["連射・雨矢", "狙撃・貫心", "貫矢・流星"],
    boss: ["強撃・圧潰", "威圧・咆哮", "反撃・轟震"],
  };

  function skillLabel(cls, i) {
    const list = SKILL_NAME[cls] || SKILL_NAME.swordsman;
    return list[Math.abs(i) % list.length];
  }

  // ---------------------------------------------------------------
  // 3Q-style combat director.
  // Every action is a scripted timeline driven by the Web Animations
  // API (no class toggling, no reflow hacks) so movement, hit-stop and
  // VFX line up on the same clock:
  //   basic : anticipate → lunge → strike → hit-stop → recover
  //   dodge : target hops back with afterimages, "MISS" pops
  //   skill : dim → portrait cut-in → charge → class VFX → multi-hit
  // ---------------------------------------------------------------
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const rnd = (a, b) => a + Math.random() * (b - a);
  const CLS_COLOR = { swordsman: "#7ad7ff", mage: "#d4a0ff", archer: "#b6ff8a", boss: "#ff6b4a" };
  let actionBusy = false;
  let pendingSkill = null;
  let bossTurn = 0;

  function heroKind(arena) {
    return arena.dataset.heroClass || window.FsqHeroClass || "swordsman";
  }

  function sideOf(arena, who) {
    return arena.querySelector(".sba-side." + who);
  }

  function actorOf(side) {
    return (side && side.querySelector(".sba-actor")) || side;
  }

  function spriteOf(side) {
    if (!side) return null;
    return (
      (side.classList.contains("show-pose") && side.querySelector(".pose-layer")) ||
      side.querySelector(".idle-layer") ||
      side.querySelector(".fighter-sprite")
    );
  }

  function boxOf(el, arena) {
    const r = el.getBoundingClientRect();
    const h = arena.getBoundingClientRect();
    return {
      x: r.left - h.left + r.width / 2,
      y: r.top - h.top + r.height / 2,
      left: r.left - h.left,
      top: r.top - h.top,
      w: r.width,
      h: r.height,
    };
  }

  function feetY(side, arena) {
    const b = boxOf(spriteOf(side) || side, arena);
    return b.top + b.h - 8;
  }

  function fxLayer(arena) {
    let l = arena.querySelector(".sba-fxlayer");
    if (!l) {
      l = document.createElement("div");
      l.className = "sba-fxlayer";
      (arena.querySelector(".sba-shake") || arena).appendChild(l);
    }
    return l;
  }

  function topLayer(arena) {
    let l = arena.querySelector(".sba-toplayer");
    if (!l) {
      l = document.createElement("div");
      l.className = "sba-toplayer";
      arena.appendChild(l);
    }
    return l;
  }

  // One-shot VFX. Static look lives in CSS (.fx-*), motion lives here so every
  // effect shares the document timeline with the fighters (hit-stop pauses all).
  const FX_ANIM = {
    "fx-arc": (v) => [
      [
        { opacity: 0, transform: "scaleX(" + v.flip + ") rotate(" + (v.rot - 70) + "deg) scale(.4)" },
        { opacity: 1, offset: 0.22 },
        { opacity: 0.9, offset: 0.7 },
        { opacity: 0, transform: "scaleX(" + v.flip + ") rotate(" + (v.rot + 60) + "deg) scale(1.3)" },
      ],
      { duration: v.big ? 400 : 340, easing: "cubic-bezier(.1,.8,.3,1)" },
    ],
    "fx-burst": () => [
      [{ opacity: 0, transform: "scale(.15)" }, { opacity: 1, offset: 0.22 }, { opacity: 0, transform: "scale(1.7)" }],
      { duration: 400, easing: "ease-out" },
    ],
    "fx-ring": () => [[{ opacity: 0.95, transform: "scale(.2)" }, { opacity: 0, transform: "scale(1.8)" }], { duration: 500, easing: "ease-out" }],
    "fx-spark": (v) => [
      [
        { opacity: 1, transform: "rotate(" + v.a + "deg) translateX(6px) scaleX(.4)" },
        { opacity: 1, offset: 0.55 },
        { opacity: 0, transform: "rotate(" + v.a + "deg) translateX(96px) scaleX(1.2)" },
      ],
      { duration: 400, easing: "ease-out" },
    ],
    "fx-dust": () => [
      [{ opacity: 0, transform: "scale(.4)" }, { opacity: 0.9, offset: 0.3 }, { opacity: 0, transform: "scale(1.8) translateY(-4px)" }],
      { duration: 400, easing: "ease-out" },
    ],
    "fx-dodge-ring": () => [
      [{ opacity: 0, transform: "scale(.4)" }, { opacity: 1, offset: 0.25 }, { opacity: 0, transform: "scale(1.6)" }],
      { duration: 460, easing: "ease-out" },
    ],
    "fx-rune": (v) => [
      [
        { opacity: 0, transform: "translate(0,10px) scaleY(.5)" },
        { opacity: 1, offset: 0.3 },
        { opacity: 0, transform: "translate(" + v.dx + "px,-90px) scaleY(1.3)" },
      ],
      { duration: 550, easing: "ease-out" },
    ],
    "fx-bolt": (v) => [
      [
        { opacity: 0, transform: "scaleY(.15) scaleX(1.6)" },
        { opacity: 1, transform: "scaleY(1) scaleX(1.1)", offset: 0.18 },
        { opacity: 1, transform: "scaleY(1) scaleX(.9)", offset: 0.6 },
        { opacity: 0, transform: "scaleY(1) scaleX(.3)" },
      ],
      { duration: 340, easing: "ease-out", delay: v.delay || 0 },
    ],
    "fx-arrow": () => [
      [
        { opacity: 0, transform: "rotate(62deg) translateX(-190px)" },
        { opacity: 1, offset: 0.15 },
        { opacity: 1, offset: 0.75 },
        { opacity: 0, transform: "rotate(62deg) translateX(24px)" },
      ],
      { duration: 280, easing: "cubic-bezier(.5,0,1,.6)" },
    ],
    "fx-shock": () => [[{ opacity: 1, transform: "scale(.2)" }, { opacity: 0, transform: "scale(1.9)" }], { duration: 550, easing: "ease-out" }],
    "fx-boulder": (v) => [
      [{ opacity: 1, transform: "translate(0,0) rotate(0)" }, { opacity: 0, transform: "translate(" + v.dx + "px," + v.dy + "px) rotate(200deg)" }],
      { duration: 600, easing: "cubic-bezier(.2,.6,.5,1)" },
    ],
    "fx-flood": () => [[{ opacity: 0 }, { opacity: 0.55, offset: 0.25 }, { opacity: 0 }], { duration: 700, easing: "ease-out" }],
    "fx-shot": () => [[{ opacity: 1 }, { opacity: 1 }], { duration: 260 }],
  };

  function fx(arena, cls, x, y, vars) {
    vars = vars || {};
    const key = cls.split(" ")[0];
    const el = document.createElement("span");
    el.className = "fx " + cls;
    if (x != null) el.style.left = x + "px";
    if (y != null) el.style.top = y + "px";
    if (vars.color) el.style.setProperty("--c", vars.color);
    fxLayer(arena).appendChild(el);
    const spec = FX_ANIM[key];
    if (spec) {
      const pair = spec(Object.assign({ flip: 1, rot: 0, a: 0, dx: 0, dy: 0, big: cls.indexOf("big") >= 0 }, vars));
      const timing = Object.assign({ fill: "both" }, pair[1]);
      const an = el.animate(pair[0], timing);
      an.onfinish = () => el.remove();
      setTimeout(() => el.remove(), (timing.duration + (timing.delay || 0)) * 2 + 1000);
    } else {
      setTimeout(() => el.remove(), 800);
    }
    return el;
  }

  function sparks(arena, x, y, color, n) {
    for (let i = 0; i < (n || 6); i++) {
      fx(arena, "fx-spark", x, y, { color: color, a: Math.round(rnd(0, 360)) });
    }
  }

  function afterimage(arena, side) {
    const img = spriteOf(side);
    if (!img) return;
    const b = boxOf(img, arena);
    const g = img.cloneNode(false);
    g.className = "fighter-ghost" + (side.classList.contains("player") ? " flip" : "");
    g.removeAttribute("id");
    g.style.cssText = "left:" + b.left + "px;top:" + b.top + "px;width:" + b.w + "px;height:" + b.h + "px";
    fxLayer(arena).appendChild(g);
    g.animate([{ opacity: 0.55 }, { opacity: 0 }], { duration: 260, easing: "ease-out" });
    setTimeout(() => g.remove(), 280);
  }

  function spawnDamage(arena, side, text, kind) {
    const img = spriteOf(side);
    const b = img ? boxOf(img, arena) : { x: arena.clientWidth / 2, top: 40 };
    const el = document.createElement("span");
    el.className = "dmg-num " + (kind || "dmg");
    el.textContent = text;
    el.style.left = b.x + rnd(-18, 18) + "px";
    el.style.top = b.top + rnd(2, 14) + "px";
    topLayer(arena).appendChild(el);
    const big = kind === "crit" || kind === "time";
    el.animate(
      [
        { transform: "translate(-50%,0) scale(.35)", opacity: 0 },
        { transform: "translate(-50%,-14px) scale(" + (big ? 1.75 : 1.5) + ")", opacity: 1, offset: 0.16 },
        { transform: "translate(-50%,-20px) scale(1)", opacity: 1, offset: 0.38 },
        { transform: "translate(-50%,-28px) scale(1)", opacity: 1, offset: 0.7 },
        { transform: "translate(-50%,-64px) scale(.9)", opacity: 0 },
      ],
      { duration: 950, easing: "cubic-bezier(.2,.7,.3,1)" }
    );
    setTimeout(() => el.remove(), 980);
  }

  function shake(arena, amp, ms) {
    const el = arena.querySelector(".sba-shake");
    if (!el) return;
    const a = amp || 6;
    const k = [];
    for (let i = 0; i < 7; i++) {
      const f = 1 - i / 6;
      k.push({ transform: "translate(" + rnd(-a, a) * f + "px," + rnd(-a, a) * f * 0.7 + "px)" });
    }
    k.push({ transform: "translate(0,0)" });
    el.animate(k, { duration: ms || 280, easing: "linear" });
  }

  function screenFlash(arena, color, peak, ms) {
    const el = document.createElement("span");
    el.className = "fx-flash";
    el.style.background = color || "#fff";
    topLayer(arena).appendChild(el);
    el.animate([{ opacity: 0 }, { opacity: peak == null ? 0.85 : peak, offset: 0.15 }, { opacity: 0 }], {
      duration: ms || 220,
      easing: "ease-out",
    });
    setTimeout(() => el.remove(), (ms || 220) + 40);
  }

  // Freeze-frame: zero the playback rate instead of pause()/play() so the
  // resume is synchronous and keeps the exact current time of every animation.
  function hitStop(arena, ms) {
    const anims = arena.getAnimations({ subtree: true }).filter((a) => a.playState === "running" && a.playbackRate !== 0);
    const rates = anims.map((a) => a.playbackRate);
    anims.forEach((a) => {
      a.playbackRate = 0;
    });
    return wait(ms).then(() =>
      anims.forEach((a, i) => {
        try {
          a.playbackRate = rates[i];
        } catch (e) {}
      })
    );
  }

  function bodyBase(side) {
    return side.classList.contains("player") ? "scaleX(-1) " : "";
  }

  function flinch(arena, side, dir, heavy) {
    const k = heavy ? 26 : 16;
    actorOf(side).animate(
      [
        { transform: "translate(0,0)" },
        { transform: "translate(" + dir * k + "px,5px) rotate(" + dir * 3 + "deg)", offset: 0.22, easing: "cubic-bezier(.1,.9,.3,1)" },
        { transform: "translate(" + dir * k * 0.55 + "px,2px)", offset: 0.62 },
        { transform: "translate(0,0)" },
      ],
      { duration: heavy ? 520 : 400, easing: "ease-out" }
    );
    const body = side.querySelector(".sba-body");
    if (body) {
      body.animate(
        [
          { filter: "brightness(1)" },
          { filter: "brightness(3.2) saturate(.3)", offset: 0.12 },
          { filter: "brightness(1.25) sepia(.35) hue-rotate(-20deg)", offset: 0.4 },
          { filter: "brightness(1)" },
        ],
        { duration: 380 }
      );
    }
    setPose(side, "hit");
    fx(arena, "fx-dust", boxOf(actorOf(side), arena).x + dir * 10, feetY(side, arena));
    setTimeout(() => setPose(side, "idle"), heavy ? 480 : 360);
  }

  async function dodge(arena, side, dir) {
    setPose(side, "dodge");
    const b = boxOf(actorOf(side), arena);
    fx(arena, "fx-dodge-ring", b.x, feetY(side, arena));
    afterimage(arena, side);
    setTimeout(() => afterimage(arena, side), 70);
    actorOf(side).animate(
      [
        { transform: "translate(0,0)" },
        { transform: "translate(" + dir * 40 + "px,-30px) rotate(" + dir * 6 + "deg)", offset: 0.3, easing: "cubic-bezier(.15,.85,.3,1)" },
        { transform: "translate(" + dir * 40 + "px,-30px) rotate(" + dir * 6 + "deg)", offset: 0.5 },
        { transform: "translate(0,0)", easing: "cubic-bezier(.4,0,.6,1)" },
      ],
      { duration: 560 }
    );
    spawnDamage(arena, side, "MISS", "miss");
    await wait(560);
    setPose(side, "idle");
  }

  function impact(arena, target, dir, color, text, kind, heavy) {
    const t = boxOf(spriteOf(target) || target, arena);
    fx(arena, "fx-burst", t.x + rnd(-8, 8), t.y + rnd(-8, 8), { color: color });
    fx(arena, "fx-ring", t.x, t.y, { color: color });
    sparks(arena, t.x, t.y, color, heavy ? 9 : 6);
    flinch(arena, target, dir, heavy);
    spawnDamage(arena, target, text, kind);
    Sfx.hit();
    shake(arena, heavy ? 10 : 5, 260);
    if (kind === "time") screenFlash(arena, "rgba(255,60,40,.9)", 0.5, 260);
  }

  async function basicAttack(arena, attacker, target, o) {
    const dir = o.fromBoss ? -1 : 1;
    const actor = actorOf(attacker);
    const a = boxOf(actor, arena);
    const t = boxOf(actorOf(target), arena);
    const gap = t.x - a.x;
    const lunge = o.melee ? gap * 0.58 : gap * 0.12;
    const D = 1080;
    const t0 = performance.now();
    let paused = 0;
    const until = (ms) => wait(Math.max(0, t0 + paused + ms - performance.now()));
    actor.animate(
      [
        { transform: "translate(0,0)" },
        { transform: "translate(" + -dir * 10 + "px,4px)", offset: 0.11, easing: "cubic-bezier(.3,.7,.5,1)" },
        { transform: "translate(" + lunge + "px,-8px)", offset: 0.27, easing: "cubic-bezier(.05,.85,.2,1)" },
        { transform: "translate(" + lunge + "px,-4px)", offset: 0.56 },
        { transform: "translate(" + lunge * 0.85 + "px,-2px)", offset: 0.7, easing: "ease-in-out" },
        { transform: "translate(0,0)" },
      ],
      { duration: D, easing: "linear" }
    );
    const body = attacker.querySelector(".sba-body");
    const B = bodyBase(attacker);
    if (body) {
      body.animate(
        [
          { transform: B + "scale(1)" },
          { transform: B + "scale(.94,1.06)", offset: 0.11 },
          { transform: B + "scale(1.08,.95) rotate(" + -dir * 6 + "deg)", offset: 0.27 },
          { transform: B + "scale(1) rotate(0)", offset: 0.45 },
          { transform: B + "scale(1)" },
        ],
        { duration: D }
      );
    }
    if (o.melee) [140, 190, 240].forEach((ms) => setTimeout(() => afterimage(arena, attacker), ms));
    await until(D * 0.2);
    setPose(attacker, "atk");
    await until(D * 0.27);
    const tx = boxOf(spriteOf(target) || target, arena);
    if (o.melee) {
      fx(arena, "fx-arc", tx.x - dir * 8, tx.y - 6, { color: o.color, flip: dir < 0 ? -1 : 1 });
    } else {
      const ax = boxOf(spriteOf(attacker) || attacker, arena);
      const shot = fx(arena, "fx-shot " + (o.cls === "archer" ? "arrow" : ""), ax.x + dir * 20, ax.y - 10, { color: o.color });
      shot.animate(
        [
          { transform: "translate(0,0) scale(.6)", opacity: 0.6 },
          { transform: "translate(" + (tx.x - ax.x - dir * 20) + "px," + (tx.y - ax.y + 6) + "px) scale(1.1)", opacity: 1 },
        ],
        { duration: 200, easing: "cubic-bezier(.3,0,.8,.4)", fill: "forwards" }
      );
      await wait(200);
      shot.remove();
      paused += 200;
    }
    if (o.miss) {
      await dodge(arena, target, dir);
    } else {
      impact(arena, target, dir, o.color, o.text, o.kind, o.heavy);
      const stop = o.heavy ? 130 : 80;
      await hitStop(arena, stop);
      paused += stop;
    }
    await until(D * 0.7);
    setPose(attacker, "idle");
    await until(D + 40);
  }

  async function cutIn(arena, attacker, o) {
    const host = topLayer(arena);
    const wrap = document.createElement("div");
    wrap.className = "sba-cutin " + (o.fromBoss ? "boss" : "hero");
    wrap.style.setProperty("--c", o.color);
    const band = document.createElement("div");
    band.className = "ci-band";
    const lines = document.createElement("div");
    lines.className = "ci-lines";
    const img = document.createElement("img");
    img.className = "ci-portrait";
    img.alt = "";
    const sp = spriteOf(attacker);
    img.src = poseUrl(attacker, "atk") || (sp && sp.src) || "";
    const name = document.createElement("div");
    name.className = "ci-name";
    name.textContent = o.name;
    const sub = document.createElement("div");
    sub.className = "ci-sub";
    sub.textContent = o.fromBoss ? "番人の技" : "必殺技";
    wrap.append(band, lines, img, name, sub);
    host.appendChild(wrap);
    const from = o.fromBoss ? "110%" : "-110%";
    const out = o.fromBoss ? "-110%" : "110%";
    const flip = o.fromBoss ? " scaleX(-1)" : "";
    const px = o.fromBoss ? "60px" : "-60px";
    const nx = o.fromBoss ? "-40px" : "40px";
    band.animate(
      [{ transform: "translateX(" + from + ") skewY(-5deg)" }, { transform: "translateX(0) skewY(-5deg)" }],
      { duration: 230, easing: "cubic-bezier(.1,.9,.2,1)", fill: "forwards" }
    );
    lines.animate(
      [{ transform: "translateX(" + (o.fromBoss ? "-30%" : "30%") + ") skewY(-5deg)", opacity: 0 }, { transform: "translateX(0) skewY(-5deg)", opacity: 1 }],
      { duration: 320, fill: "forwards" }
    );
    img.animate(
      [
        { transform: "translateX(" + px + ") scale(1.15)" + flip, opacity: 0 },
        { transform: "translateX(0) scale(1)" + flip, opacity: 1 },
      ],
      { duration: 320, easing: "cubic-bezier(.1,.9,.2,1)", fill: "forwards", delay: 60 }
    );
    [name, sub].forEach((el, i) =>
      el.animate(
        [
          { transform: "translateX(" + nx + ") scale(.8)", opacity: 0 },
          { transform: "translateX(0) scale(1.08)", opacity: 1, offset: 0.6 },
          { transform: "translateX(0) scale(1)", opacity: 1 },
        ],
        { duration: 380, easing: "ease-out", fill: "forwards", delay: 120 + i * 40 }
      )
    );
    await wait(780);
    wrap.animate([{ transform: "translateX(0)", opacity: 1 }, { transform: "translateX(" + out + ")", opacity: 0.6 }], {
      duration: 200,
      easing: "cubic-bezier(.6,0,.9,.4)",
      fill: "forwards",
    });
    await wait(200);
    wrap.remove();
  }

  async function skillAttack(arena, attacker, target, o) {
    const dir = o.fromBoss ? -1 : 1;
    const color = o.color;
    const hits = o.hits || 3;
    const dim = document.createElement("div");
    dim.className = "sba-dim";
    topLayer(arena).appendChild(dim);
    dim.animate([{ opacity: 0 }, { opacity: 0.72 }], { duration: 180, fill: "forwards" });
    await cutIn(arena, attacker, o);

    // charge
    setPose(attacker, "atk");
    const body = attacker.querySelector(".sba-body");
    const aura = attacker.querySelector(".sba-aura");
    if (body) {
      body.animate(
        [
          { filter: "brightness(1) drop-shadow(0 0 0 transparent)" },
          { filter: "brightness(1.8) drop-shadow(0 0 24px " + color + ")", offset: 0.6 },
          { filter: "brightness(1.2) drop-shadow(0 0 10px " + color + ")" },
        ],
        { duration: 480, fill: "forwards" }
      );
    }
    if (aura) {
      aura.animate([{ transform: "scale(1)", opacity: 0.7 }, { transform: "scale(2.2)", opacity: 1, offset: 0.7 }, { transform: "scale(1.4)", opacity: 0.9 }], {
        duration: 480,
      });
    }
    const actor = actorOf(attacker);
    const a = boxOf(actor, arena);
    for (let i = 0; i < 6; i++) {
      setTimeout(() => fx(arena, "fx-rune", a.x + rnd(-26, 26), feetY(attacker, arena), { color: color, dx: rnd(-14, 14) }), i * 50);
    }
    actor.animate(
      [{ transform: "translate(0,0)" }, { transform: "translate(" + dir * 6 + "px,-14px)", offset: 0.5 }, { transform: "translate(0,0)" }],
      { duration: 460, easing: "ease-in-out" }
    );
    await wait(440);
    dim.animate([{ opacity: 0.72 }, { opacity: 0.38 }], { duration: 200, fill: "forwards" });

    // VFX + hits
    const t = boxOf(spriteOf(target) || target, arena);
    const per = 150;
    const beat = async (i) => {
      const last = i === hits - 1;
      const kind = last ? (o.heavy ? "time" : "crit") : "dmg";
      impact(arena, target, dir, color, o.text(i, last), kind, last || o.heavy);
      if (last) {
        screenFlash(arena, "#fff", 0.9, 200);
        await hitStop(arena, 150);
      } else {
        await wait(per);
      }
    };
    if (o.cls === "swordsman") {
      const lunge = (t.x - a.x) * 0.62;
      const total = 240 + hits * per + 460;
      actor.animate(
        [
          { transform: "translate(0,0)" },
          { transform: "translate(" + lunge + "px,-10px)", offset: 0.14, easing: "cubic-bezier(.05,.85,.2,1)" },
          { transform: "translate(" + lunge + "px,-6px)", offset: 0.72 },
          { transform: "translate(0,0)" },
        ],
        { duration: total, easing: "linear" }
      );
      [40, 80, 120, 160].forEach((ms) => setTimeout(() => afterimage(arena, attacker), ms));
      await wait(230);
      for (let i = 0; i < hits; i++) {
        fx(arena, "fx-arc big", t.x + (i % 2 ? 14 : -14), t.y - 10 + i * 6, { color: color, rot: i * 40 - 30, flip: dir < 0 ? -1 : 1 });
        await beat(i);
      }
      await wait(420);
    } else if (o.cls === "mage") {
      fx(arena, "fx-flood", null, null, { color: color });
      for (let i = 0; i < hits; i++) {
        const x = t.x + (i - 1) * 16;
        fx(arena, "fx-bolt", x, 0, { color: color });
        fx(arena, "fx-bolt thin", x + 12, 0, { color: color, delay: 50 });
        await beat(i);
      }
      await wait(260);
    } else if (o.cls === "archer") {
      for (let i = 0; i < hits; i++) {
        for (let k = 0; k < 3; k++) {
          setTimeout(() => fx(arena, "fx-arrow", t.x + rnd(-24, 24), t.y - 12 + rnd(-20, 20), { color: color }), k * 45);
        }
        await wait(170);
        await beat(i);
      }
      await wait(220);
    } else {
      const lunge = (t.x - a.x) * 0.6;
      const total = 380 + hits * per + 460;
      actor.animate(
        [
          { transform: "translate(0,0)" },
          { transform: "translate(" + dir * 20 + "px,-76px)", offset: 0.24, easing: "cubic-bezier(.2,.8,.4,1)" },
          { transform: "translate(" + lunge + "px,-10px)", offset: 0.4, easing: "cubic-bezier(.7,0,1,.6)" },
          { transform: "translate(" + lunge + "px,-4px)", offset: 0.76 },
          { transform: "translate(0,0)" },
        ],
        { duration: total, easing: "linear" }
      );
      await wait(total * 0.4);
      fx(arena, "fx-shock", t.x, feetY(target, arena), { color: color });
      for (let i = 0; i < 7; i++) {
        fx(arena, "fx-boulder", t.x + rnd(-20, 20), feetY(target, arena), { dx: rnd(-70, 70), dy: rnd(-90, -30) });
      }
      shake(arena, 12, 320);
      for (let i = 0; i < hits; i++) await beat(i);
      await wait(420);
    }
    dim.animate([{ opacity: 0.38 }, { opacity: 0 }], { duration: 260, fill: "forwards" });
    if (body) body.animate([{ filter: "brightness(1.2) drop-shadow(0 0 10px " + color + ")" }, { filter: "brightness(1)" }], { duration: 260, fill: "forwards" });
    setPose(attacker, "idle");
    await wait(280);
    dim.remove();
    if (body) body.getAnimations().forEach((an) => an.cancel());
  }

  async function runAction(fn) {
    if (actionBusy) return false;
    actionBusy = true;
    try {
      await fn();
    } catch (e) {
      console.warn("fight action", e);
    } finally {
      actionBusy = false;
    }
    flushPending();
    return true;
  }

  function flushPending() {
    if (!pendingSkill || actionBusy || timedOut) return;
    const p = pendingSkill;
    pendingSkill = null;
    heroSkill(p.term, p.hits);
  }

  function resetFighters(arena) {
    if (!arena) return;
    actionBusy = false;
    pendingSkill = null;
    arena.querySelectorAll(".sba-side, .sba-shake").forEach((el) => {
      el.getAnimations({ subtree: true }).forEach((an) => {
        const css = (window.CSSAnimation && an instanceof CSSAnimation) || (window.CSSTransition && an instanceof CSSTransition);
        if (!css) an.cancel();
      });
      el.classList.remove("show-pose");
    });
    const top = arena.querySelector(".sba-toplayer");
    if (top) top.innerHTML = "";
    const fxl = arena.querySelector(".sba-fxlayer");
    if (fxl) fxl.innerHTML = "";
  }

  function spawnMindRune(term) {
    const arena = activeArena();
    if (!arena) return;
    const host = arena.querySelector(".sba-runes") || arena;
    const el = document.createElement("span");
    el.className = "sba-rune";
    el.textContent = term || "✦";
    el.style.setProperty("--x", 18 + Math.random() * 28 + "%");
    host.appendChild(el);
    setTimeout(() => el.remove(), 1000);
  }

  function pulseMind(arena) {
    arena.classList.remove("mind-cast");
    void arena.offsetWidth;
    arena.classList.add("mind-cast");
    const modal = $("studyModal");
    if (modal && modal.classList.contains("open")) {
      modal.classList.add("mind-flow");
      setTimeout(() => modal.classList.remove("mind-flow"), 700);
    }
    setTimeout(() => arena.classList.remove("mind-cast"), 560);
  }

  function setFightState(st) {
    st = st || {};
    fightArmed = !!st.armed;
    fightBlank = typeof st.blank === "boolean" ? st.blank : !fightArmed;
    const arena = activeArena();
    if (!arena) return;
    arena.classList.toggle("blank-page", fightBlank);
    arena.classList.toggle("armed", fightArmed && !fightBlank);
    const tension = arena.querySelector(".sba-tension") || $("battleTension");
    if (tension) {
      tension.textContent = fightArmed
        ? "用語が刃になった。番人を斬れ。"
        : fightBlank
          ? "白紙だ。番人は避け、時間だけが削られる。"
          : "まだ届かない。番人は攻撃を見切っている。";
    }
  }

  function playStrike(term, opts) {
    const arena = activeArena();
    if (!arena || timedOut) return;
    opts = opts || {};
    lastHitAt = Date.now();
    lastPlayerAct = lastHitAt;
    if (term && !opts.miss && !fightBlank) {
      if (actionBusy) {
        pendingSkill = pendingSkill ? { term: term, hits: Math.min(5, pendingSkill.hits + 1) } : { term: term, hits: 3 };
        return;
      }
      heroSkill(term, 3);
      return;
    }
    const miss = !!opts.miss || fightBlank || !fightArmed;
    runAction(() => {
      const hero = sideOf(arena, "player");
      const boss = sideOf(arena, "monster");
      if (!hero || !boss) return Promise.resolve();
      const cls = heroKind(arena);
      if (!miss) {
        battlePct = Math.min(96, battlePct + 1);
        updateBattleBars(battlePct);
      }
      return basicAttack(arena, hero, boss, {
        cls: cls,
        melee: cls === "swordsman",
        color: CLS_COLOR[cls] || CLS_COLOR.swordsman,
        miss: miss,
        text: "-" + (18 + Math.floor(Math.random() * 20)),
        kind: "dmg",
        fromBoss: false,
      });
    });
  }

  function heroSkill(term, hits) {
    const arena = activeArena();
    if (!arena || timedOut) return;
    runAction(async () => {
      const hero = sideOf(arena, "player");
      const boss = sideOf(arena, "monster");
      if (!hero || !boss) return;
      const cls = heroKind(arena);
      pulseMind(arena);
      spawnMindRune(term);
      await skillAttack(arena, hero, boss, {
        cls: cls,
        color: CLS_COLOR[cls] || CLS_COLOR.swordsman,
        name: skillLabel(cls, typingCombo),
        hits: hits || 3,
        fromBoss: false,
        text: (i, last) => "-" + ((last ? 160 : 70) + Math.floor(Math.random() * 60)),
      });
    });
  }

  function playBossStrike(opts) {
    const arena = activeArena();
    if (!arena || timedOut) return;
    opts = opts || {};
    runAction(async () => {
      const boss = sideOf(arena, "monster");
      const hero = sideOf(arena, "player");
      if (!hero || !boss) return;
      bossTurn += 1;
      const heavy = !!opts.heavy;
      if (bossTurn % 3 === 0) {
        await skillAttack(arena, boss, hero, {
          cls: "boss",
          color: CLS_COLOR.boss,
          name: skillLabel("boss", bossTurn),
          hits: 2,
          fromBoss: true,
          heavy: heavy,
          text: (i, last) => (heavy && last ? "-TIME" : "-" + (8 + Math.floor(Math.random() * 10))),
        });
      } else {
        await basicAttack(arena, boss, hero, {
          cls: "boss",
          melee: true,
          color: CLS_COLOR.boss,
          miss: false,
          heavy: heavy,
          text: heavy ? "-TIME" : "-" + (6 + Math.floor(Math.random() * 8)),
          kind: heavy ? "time" : "dmg",
          fromBoss: true,
        });
      }
    });
  }

  function playStruggle() {
    lastPlayerAct = Date.now();
  }

  function startCombatLoop() {
    lastPlayerAct = Date.now();
    combatTurn = 0;
    bossTurn = 0;
    stopCombatLoop();
    const arena = activeArena();
    if (arena) {
      arena.classList.add("fighting");
      resetFighters(arena);
    }
    combatTimer = setInterval(combatTick, 1900);
    startIdleLoop();
  }

  function stopCombatLoop() {
    if (combatTimer) {
      clearInterval(combatTimer);
      combatTimer = 0;
    }
    stopIdleLoop();
    ["studyBattleArena", "examBattleArena"].forEach((id) => {
      const el = $(id);
      if (el) el.classList.remove("fighting", "striking", "boss-striking", "clashing", "mind-cast", "combo-hot");
    });
  }

  function combatTick() {
    const arena = activeArena();
    if (!arena || arena.hidden || timedOut) return;
    if (arena.classList.contains("ko-boss") || arena.classList.contains("ko-player")) return;
    if (actionBusy || pendingSkill) return;
    if (Date.now() - lastHitAt < 700) return;
    if (fightBlank || !fightArmed) {
      if (combatTurn % 3 === 0) {
        playStrike(null, { miss: true });
      } else {
        playBossStrike({ heavy: fightBlank });
      }
    } else if (combatTurn % 2 === 0) {
      playStrike(null);
    } else {
      playBossStrike();
    }
    combatTurn += 1;
  }

  function noteTyping(hit) {
    lastPlayerAct = Date.now();
    if (hit) return;
  }

  function playKo(who, persist) {
    const arena = activeArena();
    if (!arena) return;
    stopCombatLoop();
    const side = who === "player" ? arena.querySelector(".sba-side.player") : arena.querySelector(".sba-side.monster");
    if (side) side.classList.add("ko");
    arena.classList.add(who === "player" ? "ko-player" : "ko-boss");
    const ko = arena.querySelector(".fs-ko") || $("fightKo");
    if (ko) {
      ko.hidden = false;
      ko.textContent = who === "player" ? (timedOut ? "TIME UP" : "YOU LOSE") : "K.O.";
    }
    flash(who === "player" ? "red" : "gold");
    if (who === "boss") Sfx.questClear();
    else Sfx.hit();
    if (who === "player" && !persist && !timedOut) {
      setTimeout(() => {
        if (!arena.classList.contains("ko-player") || timedOut) return;
        arena.classList.remove("ko-player");
        if (side) side.classList.remove("ko");
        if (ko) ko.hidden = true;
      }, 1600);
    }
  }

  function spawnHitFloater(text, kind) {
    const arena = activeArena();
    const host = arena || $("studyModal") || $("examModal");
    if (!host) return;
    if (arena) {
      const side = sideOf(arena, kind === "miss" ? "player" : "monster");
      if (side) {
        spawnDamage(arena, side, text, kind === "crit" ? "crit" : kind || "dmg");
        return;
      }
    }
    const f = document.createElement("span");
    f.className = "hit-floater " + (kind || "dmg");
    f.textContent = text;
    f.style.left = 22 + Math.random() * 50 + "%";
    f.style.top = 18 + Math.random() * 28 + "%";
    host.appendChild(f);
    setTimeout(() => f.remove(), 900);
  }

  function updateBattleBars(pct) {
    battlePct = Math.min(98, Math.max(8, pct));
    const bar = $("studyBattleProgress");
    if (bar) bar.style.width = battlePct + "%";
    const arena = activeArena();
    const monsterHp = (arena && arena.querySelector(".js-boss-hp")) || $("battleMonsterHp");
    if (monsterHp) monsterHp.style.width = Math.max(4, 100 - battlePct) + "%";
    paintClock();
    const combo = (arena && arena.querySelector(".sba-combo")) || $("battleCombo");
    if (combo) {
      if (typingCombo >= 3) {
        combo.hidden = false;
        combo.textContent = typingCombo + " COMBO";
      } else {
        combo.hidden = true;
      }
    }
  }

  function questLimitMs(lesson, opts) {
    const mins = Number((lesson && lesson.estimated_minutes) || 30);
    const kind = (opts && opts.bossType) || "";
    if (opts && opts.isBoss) {
      if (kind === "career_final") return 25 * 60 * 1000;
      if (kind === "monthly") return 20 * 60 * 1000;
      return 15 * 60 * 1000;
    }
    if (mins >= 45) return 15 * 60 * 1000;
    if (mins >= 25) return 10 * 60 * 1000;
    return 6 * 60 * 1000;
  }

  function formatClock(ms) {
    const s = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
  }

  function timeLeftMs() {
    if (!questStartedAt) return questLimitMsVal;
    return Math.max(0, questLimitMsVal - (Date.now() - questStartedAt));
  }

  function paintClock() {
    const left = timeLeftMs();
    const txt = formatClock(left);
    const arena = activeArena();
    if (arena) {
      const clock = arena.querySelector(".sba-clock");
      if (clock) clock.textContent = txt;
      arena.classList.toggle("hurry", left > 0 && left < 60000);
    }
    const playerMp = (arena && arena.querySelector(".js-player-hp")) || $("battlePlayerMp");
    if (playerMp) {
      const hp = left <= 0 ? 0 : Math.max(2, (left / Math.max(1, questLimitMsVal)) * 100);
      playerMp.style.width = hp + "%";
    }
  }

  function startQuestClock(lesson, opts) {
    if (clockTimer) clearInterval(clockTimer);
    timedOut = false;
    questLimitMsVal = questLimitMs(lesson, opts);
    questStartedAt = Date.now();
    paintClock();
    clockTimer = setInterval(() => {
      paintClock();
      if (!timedOut && timeLeftMs() <= 0) {
        timedOut = true;
        stopCombatLoop();
        playKo("player", true);
        toast("TIME UP", "gold");
        if (timeUpHandler) timeUpHandler();
      }
    }, 250);
  }

  function stopQuestClock() {
    if (clockTimer) {
      clearInterval(clockTimer);
      clockTimer = 0;
    }
    questStartedAt = 0;
    timedOut = false;
    document.querySelectorAll(".study-battle-arena").forEach((el) => el.classList.remove("hurry"));
  }

  function onOpenQuest(lesson, opts) {
    Sfx.questStart();
    typingCombo = 0;
    battlePct = 12;
    fightBlank = true;
    fightArmed = false;
    opts = opts || {};
    const kind = opts.bossType || (opts.isBoss ? "weekly" : "lesson");
    const idx = Math.min(4, Math.floor((lesson.estimated_minutes || 20) / 15));
    const monsterName =
      opts.monsterName ||
      (kind === "career_final"
        ? "キャリアドラゴン"
        : kind === "monthly"
          ? "学期の梟"
          : kind === "weekly"
            ? "試験の番人"
            : (REGION_LORE[idx] || REGION_LORE[0]).monster);
    paintFighters(kind, monsterName);
    const title = $("battleQuestTitle");
    if (title) title.textContent = lesson.title_ja || "QUEST";
    updateBattleBars(12);
    const modal = $("studyModal");
    if (modal && modal.classList.contains("open")) modal.classList.add("battle-mode");
    const exam = $("examModal");
    if (exam && exam.classList.contains("open")) exam.classList.add("battle-mode");
    const arena = activeArena();
    if (arena) arena.hidden = false;
    startCombatLoop();
    startQuestClock(lesson, opts);
    setFightState({ blank: true, armed: false });
    const rank = $("studyBattleRank");
    if (rank) {
      const mins = lesson.estimated_minutes || 30;
      const stars = mins >= 45 || (opts && opts.isBoss) ? "★★★" : mins >= 25 ? "★★" : "★";
      rank.textContent = "難易度 " + stars + " · " + formatClock(questLimitMsVal);
    }
    flash("teal");
    toast("QUEST START — " + (lesson.title_ja || "課題"), "teal");
    if (window.LiveHud) LiveHud.enterStudy();
  }

  function onQuestProgress(pct, hit, term) {
    updateBattleBars(pct);
    if (!hit) return;
    const now = Date.now();
    if (now - lastHitAt < 160) return;
    lastHitAt = now;
    lastPlayerAct = now;
    typingCombo += 1;
    playStrike(term);
    const arena = activeArena();
    if (arena) arena.classList.toggle("combo-hot", typingCombo >= 3);
    if (typingCombo === 5) {
      toast("コンボ！ 思考が刃になった", "gold");
      if (window.LiveHud) LiveHud.emit("cheer");
    }
    if (typingCombo >= 8 && typingCombo % 4 === 0) {
      toast("CRITICAL HIT!", "gold");
      flash("gold");
      spawnHitFloater("CRITICAL", "crit");
    }
  }

  function onTypingTick(hit) {
    noteTyping(!!hit);
  }

  function closeQuest() {
    stopCombatLoop();
    stopQuestClock();
    const modal = $("studyModal");
    if (modal) modal.classList.remove("battle-mode");
    const exam = $("examModal");
    if (exam) exam.classList.remove("battle-mode");
    typingCombo = 0;
    if (window.LiveHud) LiveHud.leaveStudy();
  }

  function showVictory(title, lines, chips) {
    playKo("boss");
    if (window.LiveHud) LiveHud.emit("win");
    Sfx.questClear();
    flash("gold");
    confetti(32);
    const modal = $("rewardModal");
    const float = $("victoryExpFloat");
    if (float) {
      const expLine = (lines || []).find((l) => /EXP/i.test(String(l)));
      float.textContent = expLine || "+EXP";
      float.classList.remove("pop");
      void float.offsetWidth;
      float.classList.add("pop");
    }
    if (modal) {
      modal.classList.add("victory-mode");
      setTimeout(() => modal.classList.remove("victory-mode"), 3400);
    }
    if ($("rewardTitle")) $("rewardTitle").textContent = title || "QUEST CLEAR!";
    if ($("rewardBody")) {
      $("rewardBody").innerHTML = (lines || [])
        .filter(Boolean)
        .map((x) => "<p>" + x + "</p>")
        .join("");
    }
    if ($("rewardChips")) {
      $("rewardChips").innerHTML = (chips || [])
        .map((c) => '<span class="chip-mini loot">' + c + "</span>")
        .join("");
    }
    if (modal) modal.classList.add("open");
    toast(title || "QUEST CLEAR!", "gold");
  }

  let pendingBossOpen = null;

  function showBossIntro(meta, onFight) {
    initLayers();
    const el = $("bossIntro");
    if (!el) {
      if (onFight) onFight();
      return;
    }
    pendingBossOpen = onFight;
    if ($("biName")) $("biName").textContent = (meta && meta.title_ja) || "試験の番人";
    if ($("biHint")) {
      $("biHint").textContent =
        (meta && meta.hint_ja) || "これまでの学習が武器になる。負けても進捗は消えない。";
    }
    if ($("biFace")) {
      const img = $("biFaceImg");
      const kind = (meta && meta.bossType) || "weekly";
      if (img) {
        img.src = bossArt(kind);
        img.hidden = false;
        $("biFace").textContent = "";
      } else {
        $("biFace").innerHTML = '<img src="' + bossArt(kind) + '" alt="">';
      }
    }
    el.classList.add("open");
    Sfx.boss();
    flash("red");
    const btn = $("biFightBtn");
    if (btn) {
      btn.onclick = () => {
        el.classList.remove("open");
        Sfx.questStart();
        const fn = pendingBossOpen;
        pendingBossOpen = null;
        if (fn) fn();
      };
    }
  }

  function onSubSwitch(name) {
    document.querySelectorAll(".fsq-section").forEach((s) => {
      s.classList.remove("world-enter");
      void s.offsetWidth;
    });
    const sec = $("fsq-" + name);
    if (sec) sec.classList.add("world-enter");
    const panel = $("mapRegionPanel");
    if (panel && name !== "map") panel.classList.remove("open");
    if (name === "map") toast("ワールドマップを開いた", "teal");
    if (name === "home") toast("拠点に帰還", "");
    if (name === "career") toast("冒険録を開いた", "");
    Sfx.click();
  }

  function decorateMapWorld(biomeIdx) {
    const world = $("mapWorld");
    if (!world) return;
    world.className = "map-world map-biome-" + Math.min(biomeIdx, 4);
    let scenery = $("mapScenery");
    if (!scenery) {
      scenery = document.createElement("div");
      scenery.id = "mapScenery";
      scenery.className = "map-scenery";
      scenery.setAttribute("aria-hidden", "true");
      const strip = world.querySelector(".map-strip");
      if (strip) world.insertBefore(scenery, strip);
      else world.appendChild(scenery);
    }
    const trees =
      '<span class="sc-tree t1"></span><span class="sc-tree t2"></span><span class="sc-tree t3"></span>';
    const rocks = '<span class="sc-rock r1"></span><span class="sc-rock r2"></span>';
    const camp = '<span class="sc-camp"></span>';
    const castle = '<span class="sc-castle"></span>';
    scenery.innerHTML = camp + trees + rocks + castle;
  }

  window.FsqWorld = {
    init: function () {
      initAmbient();
      initLayers();
      preloadFightPoses();
    },
    onEnterTab: function () {
      initAmbient();
      initLayers();
      showPortal();
    },
    renderHud: renderHud,
    renderNarrator: renderNarrator,
    checkLevelUp: checkLevelUp,
    renderMapPanel: renderMapPanel,
    setMapDepartHandler: function (fn) {
      mapDepartHandler = fn;
    },
    onOpenQuest: onOpenQuest,
    onQuestProgress: onQuestProgress,
    onTypingTick: onTypingTick,
    noteTyping: noteTyping,
    closeQuest: closeQuest,
    showVictory: showVictory,
    onSubSwitch: onSubSwitch,
    showBossIntro: showBossIntro,
    paintFighters: paintFighters,
    playStrike: playStrike,
    playBossStrike: playBossStrike,
    playKo: playKo,
    setFightState: setFightState,
    setTimeUpHandler: function (fn) {
      timeUpHandler = fn;
    },
    isTimedOut: function () {
      return !!timedOut;
    },
    bossArt: bossArt,
    showRegionTitle: showRegionTitle,
    animateMapTravel: animateMapTravel,
    decorateMapWorld: decorateMapWorld,
    toast: toast,
    flash: flash,
    confetti: confetti,
    sfx: Sfx,
    regionLore: REGION_LORE,
  };
})();
