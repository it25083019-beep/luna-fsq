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
  let battlePct = 12;
  let typingCombo = 0;
  let travelAnimating = false;

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
        '<div class="bi-face" id="biFace">👹</div>' +
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
    if (!status.selected) {
      box.innerHTML =
        '<div class="wn-inner"><span class="wn-icon">🌙</span><div><strong>冒険の大陸が目を覚ます</strong><p>クラスと進路を選ぶと、ここがあなただけのクエスト世界になる。</p></div></div>';
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

  function spawnHitFloater(text, kind) {
    const modal = $("studyModal");
    if (!modal || !modal.classList.contains("open")) return;
    const f = document.createElement("span");
    f.className = "hit-floater " + (kind || "dmg");
    f.textContent = text;
    f.style.left = 30 + Math.random() * 40 + "%";
    f.style.top = 28 + Math.random() * 20 + "%";
    modal.appendChild(f);
    setTimeout(() => f.remove(), 900);
  }

  function updateBattleBars(pct) {
    battlePct = Math.min(98, Math.max(8, pct));
    const bar = $("studyBattleProgress");
    if (bar) bar.style.width = battlePct + "%";
    const monsterHp = $("battleMonsterHp");
    const playerMp = $("battlePlayerMp");
    if (monsterHp) monsterHp.style.width = Math.max(4, 100 - battlePct) + "%";
    if (playerMp) playerMp.style.width = battlePct + "%";
    const combo = $("battleCombo");
    if (combo) {
      if (typingCombo >= 3) {
        combo.hidden = false;
        combo.textContent = typingCombo + " COMBO";
      } else {
        combo.hidden = true;
      }
    }
  }

  function onOpenQuest(lesson) {
    Sfx.questStart();
    typingCombo = 0;
    battlePct = 12;
    const rank = $("studyBattleRank");
    if (rank) {
      const mins = lesson.estimated_minutes || 30;
      rank.textContent = "難易度 " + (mins >= 45 ? "★★★" : mins >= 25 ? "★★" : "★");
    }
    const name = $("battleMonsterName");
    if (name) {
      const idx = Math.min(4, Math.floor((lesson.estimated_minutes || 20) / 15));
      name.textContent = (REGION_LORE[idx] || REGION_LORE[0]).monster;
    }
    const title = $("battleQuestTitle");
    if (title) title.textContent = lesson.title_ja || "QUEST";
    updateBattleBars(12);
    const modal = $("studyModal");
    if (modal) modal.classList.add("battle-mode");
    const arena = $("studyBattleArena");
    if (arena) arena.hidden = false;
    flash("teal");
    toast("QUEST START — " + (lesson.title_ja || "課題"), "teal");
  }

  function onQuestProgress(pct) {
    const prev = battlePct;
    updateBattleBars(pct);
    const now = Date.now();
    if (pct > prev + 1 && now - lastHitAt > 180) {
      lastHitAt = now;
      typingCombo += 1;
      Sfx.hit();
      spawnHitFloater("-" + (8 + Math.floor(Math.random() * 12)), "dmg");
      if (typingCombo === 5) toast("コンボ！ 解答が刺さっている", "gold");
      if (typingCombo === 10) {
        toast("CRITICAL HIT!", "gold");
        flash("gold");
      }
    }
  }

  function onTypingTick() {
    typingCombo = Math.min(99, typingCombo + 1);
  }

  function closeQuest() {
    const modal = $("studyModal");
    if (modal) modal.classList.remove("battle-mode");
    typingCombo = 0;
  }

  function showVictory(title, lines, chips) {
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
    if ($("biFace")) $("biFace").textContent = "👹";
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
    closeQuest: closeQuest,
    showVictory: showVictory,
    onSubSwitch: onSubSwitch,
    showBossIntro: showBossIntro,
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
