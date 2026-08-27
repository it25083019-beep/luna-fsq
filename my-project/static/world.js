(function () {
  const REGION_LORE = [
    {
      title: "始まりの平原",
      lore: "見習い冒険者が最初に踏む大地。基礎を学び、最初のクエストに挑む安全なキャンプ地。",
      tip: "ここで身につけた基礎が、後のボス戦を支える。",
    },
    {
      title: "知恵の森",
      lore: "古いコードの残響が木々の間を漂う。論理と構造を学ぶ者だけが奥へ進める試練の森。",
      tip: "詰まったらガイドを開く — 森の精霊（定石）が道を示す。",
    },
    {
      title: "試練の丘陵",
      lore: "実践課題が連なる起伏の地。書いて、直して、提出する繰り返しが力になる。",
      tip: "Paiza風の課題は「モンスター」。解答コードが武器になる。",
    },
    {
      title: "雲上の城",
      lore: "週次・月次の試験が待ち受ける高城。ここまで来た者だけが門を叩ける。",
      tip: "ボスに負けても進捗は消えない — 何度でも挑戦できる。",
    },
    {
      title: "終焉の扉",
      lore: "最終形態への扉。スキル・実績・作品が鍵となる、キャリアのゴール地点。",
      tip: "冒険録を育てれば、就活の自己PRにもなる。",
    },
  ];

  const NARRATOR_IDLE = [
    "風がクエストボードを揺らしている… 今日も一歩、未来へ進もう。",
    "装備を整え、スキルツリーを確認。準備は冒険の半分だ。",
    "学びは経験値。提出は攻撃。ガイドは魔法のヒント。",
  ];

  let lastLevel = null;
  let portalShown = false;
  let mapDepartHandler = null;

  const Sfx = {
    ctx: null,
    play(freq, dur, type, vol) {
      try {
        if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        const o = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        o.type = type || "sine";
        o.frequency.value = freq;
        g.gain.value = vol == null ? 0.035 : vol;
        o.connect(g);
        g.connect(this.ctx.destination);
        o.start();
        g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
        o.stop(this.ctx.currentTime + dur);
      } catch (_) {}
    },
    portal() {
      this.play(196, 0.35, "triangle");
      setTimeout(() => this.play(294, 0.25, "triangle"), 120);
      setTimeout(() => this.play(392, 0.4, "sine"), 240);
    },
    questStart() {
      this.play(440, 0.1);
      setTimeout(() => this.play(554, 0.12), 70);
      setTimeout(() => this.play(659, 0.18), 140);
    },
    questClear() {
      this.play(523, 0.1);
      setTimeout(() => this.play(659, 0.1), 90);
      setTimeout(() => this.play(784, 0.12), 180);
      setTimeout(() => this.play(1047, 0.28), 270);
    },
    levelUp() {
      this.play(330, 0.12);
      setTimeout(() => this.play(440, 0.12), 100);
      setTimeout(() => this.play(554, 0.12), 200);
      setTimeout(() => this.play(880, 0.35), 320);
    },
  };

  function $(id) {
    return document.getElementById(id);
  }

  function initAmbient() {
    const box = $("worldAmbient");
    if (!box || box.dataset.ready) return;
    box.dataset.ready = "1";
    box.innerHTML = "";
    for (let i = 0; i < 28; i++) {
      const p = document.createElement("span");
      p.className = "wp " + (i % 3 === 0 ? "gold" : i % 3 === 1 ? "teal" : "soft");
      p.style.left = Math.random() * 100 + "%";
      p.style.top = Math.random() * 100 + "%";
      p.style.animationDelay = Math.random() * 6 + "s";
      p.style.animationDuration = 4 + Math.random() * 5 + "s";
      box.appendChild(p);
    }
  }

  function showPortal() {
    const el = $("worldPortal");
    if (!el) return;
    if (sessionStorage.getItem("fsq_portal_seen")) return;
    sessionStorage.setItem("fsq_portal_seen", "1");
    el.classList.add("open");
    Sfx.portal();
    setTimeout(() => el.classList.remove("open"), 2200);
  }

  function expPct(status, expProgressFn) {
    const lv = status.level || 1;
    const exp = status.total_exp || 0;
    if (typeof expProgressFn === "function") return expProgressFn(exp, lv).pct;
    return Math.min(100, Math.round(((exp % 100) / 100) * 100));
  }

  function currentRegion(status, map) {
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
    if (reg) reg.textContent = currentRegion(status, map);
    const quest = $("whQuest");
    if (quest) {
      const n = status.next_lesson;
      quest.textContent = n ? n.title_ja || n.id : "クエスト探索中…";
    }
  }

  function renderNarrator(status, map) {
    const box = $("worldNarrator");
    if (!box) return;
    if (!status.selected) {
      box.innerHTML =
        '<div class="wn-inner"><span class="wn-icon">🌙</span><div><strong>冒険の大陸が目を覚ます</strong><p>クラスと進路を選ぶと、ここがあなただけのクエスト世界になる。</p></div></div>';
      return;
    }
    const idx = Math.max(
      0,
      ((map && map.stages) || []).findIndex((s) => s.current)
    );
    const lore = REGION_LORE[idx] || REGION_LORE[0];
    const next = status.next_lesson;
    const tail = next
      ? "次のクエスト「" + (next.title_ja || next.id) + "」がボードに掲示されている。"
      : NARRATOR_IDLE[Math.floor(Date.now() / 60000) % NARRATOR_IDLE.length];
    box.innerHTML =
      '<div class="wn-inner"><span class="wn-icon">📜</span><div><strong>' +
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
        setTimeout(() => ov.classList.remove("open"), 2800);
      }
    }
    lastLevel = level;
  }

  function renderMapPanel(stage, index, journeyStatus) {
    const panel = $("mapRegionPanel");
    if (!panel) return;
    const lore = REGION_LORE[index] || REGION_LORE[0];
    const icons = ["⛺", "🌲", "⛰", "🏰", "👑"];
    $("mrpIcon").textContent = icons[index] || "◆";
    $("mrpTitle").textContent = stage.label_ja || lore.title;
    $("mrpSub").textContent = stage.current
      ? "★ 現在地"
      : stage.cleared
        ? "クリア済"
        : stage.unlocked
          ? "探索可能"
          : "未開放";
    $("mrpLore").textContent = lore.lore + " " + lore.tip;
    const btn = $("mrpDepartBtn");
    if (btn) {
      const les = (journeyStatus.next_lesson || null);
      const canGo = stage.current && les && les.available && !les.completed;
      btn.disabled = !canGo;
      btn.textContent = canGo
        ? "⚔ 「" + (les.title_ja || les.id) + "」に出撃"
        : !stage.unlocked
          ? "🔒 前のエリアをクリアしよう"
          : "このエリアのクエストを確認";
      btn.onclick = () => {
        if (canGo && mapDepartHandler) mapDepartHandler(les.id);
      };
    }
    panel.classList.add("open");
  }

  function onOpenQuest(lesson) {
    Sfx.questStart();
    const rank = $("studyBattleRank");
    const bar = $("studyBattleProgress");
    if (rank) {
      const mins = lesson.estimated_minutes || 30;
      rank.textContent = "難易度 " + (mins >= 45 ? "★★★" : mins >= 25 ? "★★" : "★");
    }
    if (bar) bar.style.width = "12%";
    const modal = $("studyModal");
    if (modal) modal.classList.add("battle-mode");
  }

  function onQuestProgress(pct) {
    const bar = $("studyBattleProgress");
    if (bar) bar.style.width = Math.min(95, Math.max(12, pct)) + "%";
  }

  function closeQuest() {
    const modal = $("studyModal");
    if (modal) modal.classList.remove("battle-mode");
  }

  function showVictory(title, lines, chips) {
    Sfx.questClear();
    const modal = $("rewardModal");
    const float = $("victoryExpFloat");
    if (float) {
      const expLine = (lines || []).find((l) => /EXP/i.test(l));
      float.textContent = expLine || "+EXP";
      float.classList.remove("pop");
      void float.offsetWidth;
      float.classList.add("pop");
    }
    if (modal) {
      modal.classList.add("victory-mode");
      setTimeout(() => modal.classList.remove("victory-mode"), 3200);
    }
    $("rewardTitle").textContent = title || "QUEST CLEAR!";
    $("rewardBody").innerHTML = (lines || []).map((x) => "<p>" + x + "</p>").join("");
    $("rewardChips").innerHTML = (chips || [])
      .map((c) => '<span class="chip-mini loot">' + c + "</span>")
      .join("");
    modal.classList.add("open");
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
  }

  window.FsqWorld = {
    init: initAmbient,
    onEnterTab: function () {
      initAmbient();
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
    closeQuest: closeQuest,
    showVictory: showVictory,
    onSubSwitch: onSubSwitch,
    regionLore: REGION_LORE,
  };
})();
