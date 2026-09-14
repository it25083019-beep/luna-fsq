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
    if (pImg) {
      if (pImg.parentElement && !pImg.parentElement.classList.contains("sba-body")) {
        const wrap = document.createElement("div");
        wrap.className = "sba-body";
        pImg.parentElement.insertBefore(wrap, pImg);
        wrap.appendChild(pImg);
      }
      pImg.src = heroSprite();
      pImg.dataset.baseSrc = pImg.src;
    }
    if (bImg) {
      if (bImg.parentElement && !bImg.parentElement.classList.contains("sba-body")) {
        const wrap = document.createElement("div");
        wrap.className = "sba-body";
        bImg.parentElement.insertBefore(wrap, bImg);
        wrap.appendChild(bImg);
      }
      bImg.src = bossArt(kind || "lesson");
      bImg.dataset.baseSrc = bImg.src;
    }
    if (pName) pName.textContent = window.FsqHeroName || "YOU";
    if (bName) bName.textContent = monsterName || "課題モンスター";
    const cls = window.FsqHeroClass || "swordsman";
    arena.dataset.heroClass = cls;
    arena.dataset.bossKind = kind || "lesson";
    const heroWrap = arena.querySelector(".sba-side.player");
    const bossWrap = arena.querySelector(".sba-side.monster");
    if (heroWrap) {
      heroWrap.dataset.pack = cls;
      heroWrap.dataset.busy = "0";
    }
    if (bossWrap) {
      bossWrap.dataset.pack = kind === "lesson" ? "slime" : "knight";
      bossWrap.dataset.busy = "0";
    }
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
    if (bossWrap) bossWrap.classList.remove("ko", "atk-boss", "hit", "rush", "dodge");
    if (heroWrap) heroWrap.classList.remove("ko", "hit", "struggle", "rush", "dodge", "atk-swordsman", "atk-mage", "atk-archer");
  }

  const FIGHT_POSES = {
    swordsman: {
      idle: "/static/rpg/fight/swordsman_idle.png",
      atk: "/static/rpg/fight/swordsman_atk.png",
      hit: "/static/rpg/fight/swordsman_hit.png",
    },
    mage: {
      idle: "/static/rpg/fight/mage_idle.png",
      atk: "/static/rpg/fight/mage_atk.png",
    },
    archer: {
      idle: "/static/rpg/fight/archer_idle.png",
      atk: "/static/rpg/fight/archer_atk.png",
    },
    slime: {
      idle: "/static/rpg/fight/slime_idle.png",
      atk: "/static/rpg/fight/slime_atk.png",
      dodge: "/static/rpg/fight/slime_dodge.png",
      hit: "/static/rpg/fight/slime_hit.png",
    },
    knight: {
      atk: "/static/rpg/fight/knight_atk.png",
    },
  };

  let idleTimer = 0;
  let idleFlip = 0;

  function poseUrl(side, pose) {
    const pack = (side && side.dataset.pack) || "";
    const map = FIGHT_POSES[pack];
    return map && map[pose];
  }

  function setPose(side, pose) {
    if (!side) return;
    const img = side.querySelector(".fighter-sprite");
    if (!img) return;
    const base = img.dataset.baseSrc;
    if (pose === "base") {
      if (base) img.src = base;
      return;
    }
    const url = poseUrl(side, pose);
    img.src = url || base || img.src;
  }

  function busy(side, on) {
    if (side) side.dataset.busy = on ? "1" : "0";
  }

  function releaseBusy(side, ms) {
    setTimeout(() => {
      busy(side, false);
      setPose(side, idleFlip ? "idle" : "base");
    }, ms || 640);
  }

  function preloadFightPoses() {
    Object.keys(FIGHT_POSES).forEach((pack) => {
      Object.keys(FIGHT_POSES[pack]).forEach((pose) => {
        const im = new Image();
        im.src = FIGHT_POSES[pack][pose];
      });
    });
  }

  function startIdleLoop() {
    if (idleTimer) clearInterval(idleTimer);
    idleFlip = 0;
    idleTimer = setInterval(() => {
      idleFlip ^= 1;
      const arena = activeArena();
      if (!arena || timedOut) return;
      arena.querySelectorAll(".sba-side").forEach((side) => {
        if (side.dataset.busy === "1") return;
        setPose(side, idleFlip ? "idle" : "base");
      });
    }, 460);
  }

  function stopIdleLoop() {
    if (idleTimer) {
      clearInterval(idleTimer);
      idleTimer = 0;
    }
  }

  const SKILL_NAME = {
    swordsman: ["斬撃", "一閃", "剣技"],
    mage: ["詠唱", "魔力弾", "術式"],
    archer: ["連射", "狙撃", "貫矢"],
    boss: ["強撃", "威圧", "反撃"],
  };

  function skillLabel(cls, i) {
    const list = SKILL_NAME[cls] || SKILL_NAME.swordsman;
    return list[i % list.length];
  }

  function shotKind(cls) {
    if (cls === "mage") return "bolt";
    if (cls === "archer") return "arrow";
    return "slash";
  }

  function showSkillName(arena, text, fromBoss) {
    const el = arena.querySelector(".sba-skill-name");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("from-boss", !!fromBoss);
    el.classList.remove("go");
    void el.offsetWidth;
    el.classList.add("go");
    setTimeout(() => el.classList.remove("go"), 720);
  }

  function fireShot(arena, kind) {
    const shot = arena.querySelector(".sba-shot");
    if (!shot) return;
    shot.className = "sba-shot " + kind + " go";
    void shot.offsetWidth;
    setTimeout(() => shot.classList.remove("go"), 520);
  }

  function burstClash(arena, fromBoss) {
    const clash = arena.querySelector(".sba-clash");
    if (!clash) return;
    clash.classList.toggle("from-boss", !!fromBoss);
    clash.classList.remove("go");
    void clash.offsetWidth;
    clash.classList.add("go");
    setTimeout(() => clash.classList.remove("go"), 480);
  }

  function clearFighterState(el) {
    if (!el) return;
    el.classList.remove(
      "rush",
      "hit",
      "dodge",
      "struggle",
      "atk-swordsman",
      "atk-mage",
      "atk-archer",
      "atk-boss"
    );
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

  function spawnGhost(side) {
    if (!side) return;
    const body = side.querySelector(".sba-body");
    const img = side.querySelector(".fighter-sprite");
    if (!body || !img) return;
    const g = img.cloneNode(true);
    g.className = "fighter-ghost";
    g.removeAttribute("id");
    body.appendChild(g);
    setTimeout(() => g.remove(), 380);
  }

  function hitFreeze(arena, ms) {
    if (!arena) return;
    arena.classList.add("freeze");
    setTimeout(() => arena.classList.remove("freeze"), ms || 90);
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
    const miss = !!opts.miss || (fightBlank && !term);
    lastHitAt = Date.now();
    lastPlayerAct = lastHitAt;
    const cls = arena.dataset.heroClass || window.FsqHeroClass || "swordsman";
    arena.classList.remove("striking", "clashing", "boss-striking");
    void arena.offsetWidth;
    arena.classList.add("striking");
    if (term && !miss) {
      pulseMind(arena);
      showSkillName(arena, skillLabel(cls, typingCombo), false);
      spawnMindRune(term);
    } else if (miss) {
      showSkillName(arena, "空振り", false);
    } else {
      showSkillName(arena, skillLabel(cls, combatTurn), false);
    }
    fireShot(arena, shotKind(cls));
    const hero = arena.querySelector(".sba-side.player");
    const boss = arena.querySelector(".sba-side.monster");
    clearFighterState(hero);
    if (hero) {
      busy(hero, true);
      setPose(hero, "atk");
      void hero.offsetWidth;
      hero.classList.add("rush", "atk-" + cls);
      spawnGhost(hero);
      setTimeout(() => spawnGhost(hero), 90);
      setTimeout(() => hero.classList.remove("rush", "atk-swordsman", "atk-mage", "atk-archer"), 640);
      releaseBusy(hero, 700);
    }
    setTimeout(() => {
      if (miss) {
        if (boss) {
          busy(boss, true);
          setPose(boss, "dodge");
          clearFighterState(boss);
          void boss.offsetWidth;
          boss.classList.add("dodge");
          setTimeout(() => boss.classList.remove("dodge"), 480);
          releaseBusy(boss, 520);
        }
        spawnHitFloater("回避", "miss");
        return;
      }
      arena.classList.add("clashing");
      burstClash(arena, false);
      hitFreeze(arena, 80);
      if (boss) {
        busy(boss, true);
        setPose(boss, "hit");
        clearFighterState(boss);
        void boss.offsetWidth;
        boss.classList.add("hit");
        setTimeout(() => boss.classList.remove("hit"), 400);
        releaseBusy(boss, 480);
      }
      Sfx.hit();
      setTimeout(() => arena.classList.remove("clashing"), 420);
    }, 240);
  }

  function playBossStrike(opts) {
    const arena = activeArena();
    if (!arena || timedOut) return;
    opts = opts || {};
    arena.classList.remove("boss-striking", "clashing", "striking");
    void arena.offsetWidth;
    arena.classList.add("boss-striking");
    showSkillName(arena, skillLabel("boss", Math.floor(Math.random() * 3)), true);
    fireShot(arena, "boss");
    const boss = arena.querySelector(".sba-side.monster");
    const hero = arena.querySelector(".sba-side.player");
    clearFighterState(boss);
    if (boss) {
      busy(boss, true);
      setPose(boss, "atk");
      void boss.offsetWidth;
      boss.classList.add("rush", "atk-boss");
      spawnGhost(boss);
      setTimeout(() => spawnGhost(boss), 90);
      setTimeout(() => boss.classList.remove("rush", "atk-boss"), 640);
      releaseBusy(boss, 700);
    }
    setTimeout(() => {
      arena.classList.add("clashing");
      burstClash(arena, true);
      hitFreeze(arena, opts.heavy ? 110 : 80);
      if (hero) {
        busy(hero, true);
        setPose(hero, "hit");
        clearFighterState(hero);
        void hero.offsetWidth;
        hero.classList.add("hit");
        setTimeout(() => hero.classList.remove("hit"), 400);
        releaseBusy(hero, 480);
      }
      spawnHitFloater(opts.heavy ? "-TIME" : "-" + (6 + Math.floor(Math.random() * 8)), "dmg");
      Sfx.hit();
      setTimeout(() => arena.classList.remove("clashing"), 420);
    }, 240);
  }

  function playStruggle() {
    lastPlayerAct = Date.now();
  }

  function startCombatLoop() {
    lastPlayerAct = Date.now();
    combatTurn = 0;
    stopCombatLoop();
    const arena = activeArena();
    if (arena) arena.classList.add("fighting");
    combatTimer = setInterval(combatTick, 1600);
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
    const now = Date.now();
    if (now - lastHitAt < 700) return;
    if (fightBlank || !fightArmed) {
      if (combatTurn % 3 === 0) {
        playStrike(null, { miss: true });
      } else {
        playBossStrike({ heavy: fightBlank });
      }
    } else if (combatTurn % 2 === 0) {
      playStrike(null);
      spawnHitFloater("-" + (5 + Math.floor(Math.random() * 7)), "dmg");
      battlePct = Math.min(96, battlePct + 1);
      updateBattleBars(battlePct);
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
    Sfx.hit();
    playStrike(term);
    spawnHitFloater("-" + (14 + Math.floor(Math.random() * 22)), "dmg");
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
