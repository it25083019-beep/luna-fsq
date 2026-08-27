(function () {
  const CLASSES = [
    { id: "swordsman", label: "剣士", icon: "⚔️" },
    { id: "mage", label: "魔法使い", icon: "🪄" },
    { id: "archer", label: "弓使い", icon: "🏹" },
  ];
  const CLASS_DESC = {
    swordsman: "近接・バランス型。粘り強く基礎を積む冒険者向き。",
    mage: "知識と分析で道を開くタイプ。学習量が多い職に相性◎。",
    archer: "集中と精度。観察・デザイン・精密作業向き。",
  };
  const SKILL_CLS = {
    pink: "linear-gradient(135deg,#ff5d9d,#ff91c8)",
    blue: "linear-gradient(135deg,#497cff,#31d2ff)",
    yellow: "linear-gradient(135deg,#f6b61f,#ffdb68)",
    green: "linear-gradient(135deg,#1bb874,#6de8b8)",
    purple: "linear-gradient(135deg,#7a5cff,#b47aff)",
    orange: "linear-gradient(135deg,#ff7a38,#ffbf42)",
  };
  const QUICK = {
    health: ["睡眠7時間目標", "水を意識する", "少し疲れた", "調子いい"],
    money: ["時給を記録", "欲しいものメモ", "今月の支出", "貯金目標"],
    schedule: ["テスト日程", "バイトシフト", "締切あり", "空き時間"],
  };
  const MAP_POSITIONS = [
    { left: "12%", top: "55%" },
    { left: "35%", top: "25%" },
    { left: "58%", top: "45%" },
    { left: "78%", top: "20%" },
    { left: "88%", top: "60%" },
  ];
  const BOSS_LABEL = { weekly: "週次ボス", monthly: "月次ボス", career_final: "最終ボス" };
  const EVOLUTION_RANKS = [
    { id: "novice", label: "見習い" },
    { id: "intermediate", label: "中級" },
    { id: "veteran", label: "熟練" },
    { id: "saint", label: "聖級" },
  ];

  let token = LunaAuth.getToken();
  let busy = false;
  let luna = null;
  let chatStarted = false;
  let firstChat = true;
  let voiceOn = localStorage.getItem("luna_voice") !== "0";
  let lunaAudio = null;
  let lunaAudioUrl = null;
  let ttsFailStreak = 0;
  let speakSeq = 0;
  let audioUnlocked = false;
  let voicesReady = false;
  let currentTab = "luna";
  let currentModule = "health";
  let stateData = { level: 1, total_exp: 0, companion_name: null, user_display_name: null };
  let rpgData = { class_id: null, region_id: "tutorial_plains", active_quests: [] };
  let regions = [];
  let classLabels = {};
  let selectedClass = localStorage.getItem("luna_class") || "swordsman";
  let journeyStatus = { selected: false, classes: [], careers: [] };
  let journeyMap = { selected: false, stages: [], lessons: [], bosses: [] };
  let onboardStep = "class";
  let reselectJourney = false;

  const errEl = document.getElementById("err");
  const lunaMainView = document.getElementById("lunaMainView");
  const settingsView = document.getElementById("settingsView");
  let calCursor = new Date();
  let selectedDate = null;
  let allScheduleEvents = [];
  let datesWithEvents = new Set();

  const WEEKDAY_JA = ["日", "月", "火", "水", "木", "金", "土"];

  function weekdayJaFromIso(iso) {
    const d = new Date(iso + "T12:00:00");
    return WEEKDAY_JA[d.getDay()] || "";
  }

  function askRepeatSameWeekday(iso) {
    const wd = weekdayJaFromIso(iso);
    return confirm(
      "この予定を、これから先の同じ曜日にも繰り返しますか？\n\n" +
        "OK = 今後も毎週「" +
        wd +
        "曜日」に同じ予定を入れる（最初は約1年分）\n" +
        "キャンセル = この日だけ"
    );
  }

  let pendingExtendIds = [];

  function readExtendDismissed() {
    try {
      return JSON.parse(sessionStorage.getItem("schedExtendDismissed") || "{}") || {};
    } catch (_) {
      return {};
    }
  }

  function writeExtendDismissed(map) {
    try {
      sessionStorage.setItem("schedExtendDismissed", JSON.stringify(map || {}));
    } catch (_) {}
  }

  function showExtendHorizonPrompt(prompt) {
    const box = document.getElementById("extendHorizonPrompt");
    const msg = document.getElementById("extendHorizonMsg");
    if (!box || !msg) return;
    if (!prompt || !prompt.needed || !(prompt.templates || []).length) {
      box.classList.remove("open");
      pendingExtendIds = [];
      return;
    }
    const dismissed = readExtendDismissed();
    const due = (prompt.templates || []).filter((t) => {
      const key = String(t.id || "");
      return key && dismissed[key] !== t.horizon_end;
    });
    if (!due.length) {
      box.classList.remove("open");
      pendingExtendIds = [];
      return;
    }
    pendingExtendIds = due.map((t) => t.id).filter(Boolean);
    msg.textContent = prompt.message_ja || "繰り返し予定の1年分がまもなく終わります。あと1年分を続けますか？";
    box.classList.add("open");
  }

  async function extendRecurringHorizons() {
    const ids = pendingExtendIds.slice();
    try {
      await api("/schedule/recurring/extend", {
        method: "POST",
        body: JSON.stringify({ template_ids: ids.length ? ids : null, days: 365 }),
      });
      const box = document.getElementById("extendHorizonPrompt");
      if (box) box.classList.remove("open");
      pendingExtendIds = [];
      await loadScheduleView({ preserveCursor: true });
    } catch (e) {
      setErr(e.message);
    }
  }

  function dismissExtendHorizonPrompt() {
    const dismissed = readExtendDismissed();
    const last = window.__lastExtendPrompt;
    if (last && Array.isArray(last.templates)) {
      last.templates.forEach((t) => {
        if (t && t.id) dismissed[String(t.id)] = t.horizon_end || "dismissed";
      });
    } else {
      (pendingExtendIds || []).forEach((id) => {
        dismissed[String(id)] = "dismissed";
      });
    }
    writeExtendDismissed(dismissed);
    const box = document.getElementById("extendHorizonPrompt");
    if (box) box.classList.remove("open");
    pendingExtendIds = [];
  }
  const chartInstances = {};

  function fmtYen(n) {
    return "¥" + Number(n || 0).toLocaleString("ja-JP");
  }

  function destroyChart(key) {
    if (chartInstances[key]) {
      chartInstances[key].destroy();
      delete chartInstances[key];
    }
  }

  function makeChart(key, canvasId, config) {
    destroyChart(key);
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return;
    chartInstances[key] = new Chart(canvas, config);
  }

  function fmtDateJa(iso) {
    const d = new Date(iso + "T12:00:00");
    const wd = ["日", "月", "火", "水", "木", "金", "土"][d.getDay()];
    return d.getFullYear() + "年" + (d.getMonth() + 1) + "月" + d.getDate() + "日（" + wd + "）";
  }

  function todayIso() {
    const d = new Date();
    return (
      d.getFullYear() +
      "-" +
      String(d.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(d.getDate()).padStart(2, "0")
    );
  }

  function openSubview(name) {
    closeAllSubviews();
    document.getElementById("sub-" + name).classList.remove("hidden");
    document.body.classList.add("subview-open");
    if (name === "schedule") {
      selectedDate = todayIso();
      loadScheduleView();
    }
    if (name === "health") loadHealthView();
    if (name === "money") loadMoneyView();
    if (name === "goals") loadGoalsView();
  }

  function closeSubview(name) {
    const el = document.getElementById("sub-" + name);
    if (el) el.classList.add("hidden");
  }

  function closeAllSubviews() {
    ["schedule", "health", "money", "goals"].forEach(closeSubview);
    document.body.classList.remove("subview-open");
  }

  function setNavActive(name) {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.nav === name));
  }

  function setLunaView(view) {
    const isMain = view === "main";
    const isSettings = view === "settings";
    lunaMainView.classList.toggle("hidden", !isMain);
    settingsView.classList.toggle("open", isSettings);
  }

  function expForLevel(lv) {
    return Math.max(100, Math.pow(Math.max(1, lv), 2) * 100);
  }

  function expProgress(totalExp, level) {
    const curFloor = Math.pow(Math.max(0, level - 1), 2) * 100;
    const next = expForLevel(level);
    const inLevel = Math.max(0, totalExp - curFloor);
    const need = Math.max(1, next - curFloor);
    return { cur: inLevel, need, pct: Math.min(100, Math.round((inLevel / need) * 100)) };
  }

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (token) headers.Authorization = "Bearer " + token;
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    let data = null;
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok) throw new Error(LunaAuth.formatApiError(res, data));
    return data;
  }

  function setErr(msg) {
    if (errEl) errEl.textContent = msg || "";
  }

  function switchTab(name) {
    currentTab = name;
    setNavActive(name);
    if (name === "health" || name === "money" || name === "goals") {
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      document.getElementById("tab-luna").classList.add("active");
      closeAllSubviews();
      openSubview(name);
      window.scrollTo(0, 0);
      return;
    }
    closeAllSubviews();
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    const panel = document.getElementById("tab-" + name);
    if (panel) panel.classList.add("active");
    if (name === "luna") {
      setLunaView("main");
      loadHomeSummary();
      if (!chatStarted) startChat();
    }
    if (name === "fsq") loadFsqTab();
    window.scrollTo(0, 0);
  }

  function switchFsqSub(name) {
    document.querySelectorAll(".fsq-sub").forEach((b) => b.classList.toggle("active", b.dataset.fsq === name));
    document.querySelectorAll(".fsq-section").forEach((s) => s.classList.remove("active"));
    document.getElementById("fsq-" + name).classList.add("active");
  }

  function loadFsqTab() {
    loadJourney().catch((e) => setErr(e.message));
  }

  function showFsqOnboarding(show) {
    const onboard = document.getElementById("fsq-onboard");
    const sub = document.getElementById("fsqSubnav");
    const sections = ["fsq-home", "fsq-map", "fsq-career"];
    if (sub) sub.style.display = show ? "none" : "flex";
    if (onboard) {
      onboard.classList.toggle("active", !!show);
      onboard.style.display = "";
    }
    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (show) el.classList.remove("active");
    });
    if (!show) {
      document.querySelectorAll(".fsq-sub").forEach((b) => b.classList.toggle("active", b.dataset.fsq === "home"));
      const home = document.getElementById("fsq-home");
      if (home) home.classList.add("active");
      document.querySelectorAll("#fsq-map, #fsq-career").forEach((el) => el.classList.remove("active"));
    }
  }

  function applyJourneyUi() {
    const needOnboard = reselectJourney || !journeyStatus.selected;
    showFsqOnboarding(needOnboard);
    if (needOnboard) {
      renderClassPicker();
      const classStep = document.getElementById("onboardClassStep");
      const careerStep = document.getElementById("onboardCareerStep");
      if (classStep) classStep.style.display = onboardStep === "class" ? "block" : "none";
      if (careerStep) careerStep.style.display = onboardStep === "career" ? "block" : "none";
      if (onboardStep === "career") renderCareerPicker();
      const prev = document.getElementById("onboardEvolutionPreview");
      if (prev) prev.style.display = onboardStep === "class" ? "block" : "none";
      if (onboardStep === "class") {
        renderEvolutionGrid("onboardEvoGrid", selectedClass, "novice", "onboardEvoHint");
      }
      return;
    }
    renderHomeHeader();
    renderSkills();
    renderNextLesson();
    renderMap();
    renderMapDailyQuest();
    renderLessons();
    renderBosses();
    renderCareerPortfolio();
  }

  async function loadJourney() {
    try {
      const [st, mp] = await Promise.all([api("/journey/status"), api("/journey/map")]);
      journeyStatus = st || { selected: false, classes: [], careers: [] };
      journeyMap = mp || { selected: false, stages: [], lessons: [], bosses: [] };
      if (st && st.class_id) selectedClass = st.class_id;
    } catch (e) {
      setErr(e.message);
      try {
        const cat = await api("/journey/careers");
        journeyStatus = Object.assign({ selected: false }, journeyStatus, {
          classes: cat.classes || [],
          careers: cat.careers || [],
        });
      } catch (_) {
        journeyStatus = Object.assign({ selected: false, classes: [], careers: [] }, journeyStatus);
      }
      journeyMap = { selected: false, stages: [], lessons: [], bosses: [] };
    }
    applyJourneyUi();
  }

  function renderClassPicker() {
    const el = document.getElementById("classPicker");
    if (!el) return;
    el.innerHTML = "";
    const list = (journeyStatus.classes && journeyStatus.classes.length ? journeyStatus.classes : CLASSES).map((c) => ({
      id: c.id,
      label: c.label_ja || c.label,
      icon: CLASSES.find((x) => x.id === c.id)?.icon || "⚔️",
    }));
    list.forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "class-btn" + (c.id === selectedClass ? " active" : "");
      b.innerHTML =
        '<img class="class-preview" src="' +
        evolutionSpritePath(c.id, "novice") +
        '" alt=""/>' +
        c.label;
      b.onclick = () => {
        selectedClass = c.id;
        localStorage.setItem("luna_class", c.id);
        renderEvolutionGrid("onboardEvoGrid", selectedClass, "novice", "onboardEvoHint");
        onboardStep = "career";
        applyJourneyUi();
      };
      el.appendChild(b);
    });
  }

  function renderCareerPicker() {
    const el = document.getElementById("careerPicker");
    if (!el) return;
    el.innerHTML = "";
    const careers = journeyStatus.careers || [];
    careers.forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "career-pick" + (c.full_curriculum ? "" : " stub");
      b.innerHTML =
        "<strong>" +
        (c.title_ja || c.id) +
        "</strong><span>" +
        (c.short_blurb || "") +
        '</span><span class="tag">' +
        (c.full_curriculum ? "フル教材" : "ミニ教材") +
        "</span>";
      b.onclick = () => selectJourneyCareer(c.id);
      el.appendChild(b);
    });
  }

  async function selectJourneyCareer(careerId) {
    try {
      const res = await api("/journey/select", {
        method: "POST",
        body: JSON.stringify({ class_id: selectedClass, career_id: careerId }),
      });
      journeyStatus = res.status || journeyStatus;
      journeyMap = res.map || journeyMap;
      reselectJourney = false;
      onboardStep = "class";
      if (luna) luna.applyEmotion("cheer", 1500);
      applyJourneyUi();
      await refreshCore();
    } catch (e) {
      setErr(e.message);
    }
  }

  function classLabel(id) {
    if (!id) return "冒険者";
    return classLabels[id] || CLASSES.find((c) => c.id === id)?.label || id;
  }

  function evolutionSpritePath(classId, rankId) {
    const cls = classId || "swordsman";
    const rank = rankId || "novice";
    return "/static/rpg/characters/" + cls + "_" + rank + "_stand.png";
  }

  function portraitSpritePath(classId, rankId) {
    const cls = classId || "swordsman";
    const rank = rankId || "novice";
    return "/static/rpg/characters/" + cls + "_" + rank + ".png";
  }

  function rankOrder(rankId) {
    const i = EVOLUTION_RANKS.findIndex((r) => r.id === rankId);
    return i >= 0 ? i : 0;
  }

  function renderEvolutionGrid(containerId, classId, currentRankId, labelId) {
    const grid = document.getElementById(containerId);
    if (!grid || !classId) return;
    const cur = currentRankId || "novice";
    const curIdx = rankOrder(cur);
    grid.innerHTML = EVOLUTION_RANKS.map((r, i) => {
      const cls = ["evo-cell"];
      if (r.id === cur) cls.push("current");
      else if (i < curIdx) cls.push("reached");
      else cls.push("locked");
      return (
        '<div class="' +
        cls.join(" ") +
        '"><img src="' +
        evolutionSpritePath(classId, r.id) +
        '" alt="' +
        r.label +
        '"/><div class="lbl">' +
        r.label +
        "</div></div>"
      );
    }).join("");
    if (labelId) {
      const lbl = document.getElementById(labelId);
      if (lbl) lbl.textContent = EVOLUTION_RANKS[curIdx]?.label || "見習い";
    }
  }

  const GEAR_SLOT_JA = { weapon: "武器", armor: "防具", accessory: "装飾", artifact: "証" };
  const GEAR_SLOT_ICO = { weapon: "⚔", armor: "🛡", accessory: "💠", artifact: "📜" };
  const CLASS_HELD_ICO = {
    swordsman: { weapon: "⚔", armor: "🛡", accessory: "✨", artifact: "🏅" },
    mage: { weapon: "🪄", armor: "📖", accessory: "🔮", artifact: "🏅" },
    archer: { weapon: "🏹", armor: "🪶", accessory: "🎯", artifact: "🏅" },
  };

  function applyAppearance(wrap, img, appearance) {
    if (!wrap || !img) return;
    const ap = appearance || {};
    const standee = wrap.classList.contains("standee");
    wrap.className = "hero-avatar " + (standee ? "standee " : "") + (ap.css_classes || "");
    const classId = ap.class_id || journeyStatus.class_id || selectedClass;
    const rankId = ap.rank_id || journeyStatus.rank_id || "novice";
    let evo = ap.evolution_sprite || ap.sprite || (classId ? evolutionSpritePath(classId, rankId) : null);
    if (evo && typeof evo === "string" && evo.indexOf("_stand.png") < 0 && /\/static\/rpg\/characters\/[^/]+\.png$/.test(evo)) {
      evo = evo.replace(/\.png$/, "_stand.png");
    }
    if (evo && classId) {
      wrap.classList.add("has-evolution");
      if (standee) wrap.classList.add("standee");
      img.src = evo;
      img.alt = (ap.class_label_ja || classLabel(classId)) + " " + (ap.rank_label_ja || journeyStatus.rank_ja || "");
    } else if (ap.sprite) {
      img.src = ap.sprite;
    }
    const alive = document.getElementById("homeHeroAlive");
    if (alive) {
      alive.className = "hero-alive class-" + (classId || "swordsman");
    }
    renderHeldProps(appearance, classId);
    const tag = document.getElementById("homeAvatarClass");
    if (tag) tag.textContent = ap.class_label_ja || classLabel(ap.class_id) || "—";
    const emblem = document.getElementById("homeAvatarEmblem");
    if (emblem) emblem.textContent = ap.class_emblem_ja || (ap.class_label_ja || "旅")[0] || "旅";
  }

  function renderHeldProps(appearance, classId) {
    const box = document.getElementById("homeHeldProps");
    if (!box) return;
    const details = (appearance && appearance.equipped_details) || [];
    const bySlot = {};
    details.forEach((d) => {
      if (d && d.slot) bySlot[d.slot] = d;
    });
    const icos = CLASS_HELD_ICO[classId] || CLASS_HELD_ICO.swordsman;
    const slots = ["weapon", "armor", "accessory", "artifact"];
    box.innerHTML = slots
      .map((slot) => {
        const row = bySlot[slot];
        const empty = row ? "" : " empty";
        const title = row ? row.label_ja || row.id : GEAR_SLOT_JA[slot] + " 未装備";
        return (
          '<span class="held-prop ' +
          slot +
          empty +
          '" title="' +
          title +
          '"><i class="ring" aria-hidden="true"></i><span class="glyph">' +
          (icos[slot] || GEAR_SLOT_ICO[slot] || "◆") +
          "</span></span>"
        );
      })
      .join("");
  }

  function renderGearPanel(appearance, inventory) {
    const panel = document.getElementById("homeGearPanel");
    if (!panel) return;
    const details = (appearance && appearance.equipped_details) || [];
    const slots = ["weapon", "armor", "accessory", "artifact"];
    const bySlot = {};
    details.forEach((d) => {
      bySlot[d.slot] = d;
    });
    (inventory || []).forEach((it) => {
      if (it && it.slot && !bySlot[it.slot]) bySlot[it.slot] = it;
    });
    const classId = (appearance && appearance.class_id) || journeyStatus.class_id || selectedClass;
    const icos = CLASS_HELD_ICO[classId] || GEAR_SLOT_ICO;
    panel.innerHTML = slots
      .map((slot) => {
        const row = bySlot[slot];
        const label = row ? row.label_ja || row.id || "装備中" : "未装備";
        const empty = row ? "" : " empty";
        return (
          '<div class="gear-slot' +
          empty +
          '" data-slot="' +
          slot +
          '"><span class="ico" aria-hidden="true">' +
          (icos[slot] || GEAR_SLOT_ICO[slot] || "◆") +
          '</span><span class="k">' +
          (GEAR_SLOT_JA[slot] || slot) +
          '</span><span class="v">' +
          label +
          "</span></div>"
        );
      })
      .join("");
  }

  function renderHomeHeader() {
    const cls = journeyStatus.class_id || rpgData.class_id || selectedClass;
    const user = stateData.user_display_name || "学習者";
    const lv = journeyStatus.level || stateData.level || 1;
    const exp = journeyStatus.total_exp || stateData.total_exp || 0;
    const prog = expProgress(exp, lv);
    const done = journeyStatus.completed_count || 0;
    const rankJa = journeyStatus.rank_ja || "見習い";
    const badge = document.getElementById("homeClassBadge");
    if (badge) {
      badge.textContent =
        "クラス：" +
        (journeyStatus.class_ja || classLabel(cls)) +
        " ／ 習熟：" +
        rankJa;
    }
    const chip = document.getElementById("homeRankChip");
    if (chip) chip.textContent = rankJa;
    const plate = document.getElementById("homeNameplate");
    if (plate) plate.textContent = (journeyStatus.class_ja || classLabel(cls) || "PARTY").toUpperCase();
    const role = document.getElementById("homeRoleName");
    if (role) role.textContent = journeyStatus.career_title_ja || user;
    const desc = document.getElementById("homeRoleDesc");
    if (desc) {
      desc.textContent = journeyStatus.selected
        ? "職業学習 " +
          done +
          " 単元完了。マップを進めてボスに挑もう。"
        : CLASS_DESC[cls] || CLASS_DESC.swordsman;
    }
    const expL = document.getElementById("homeExpLabel");
    if (expL) expL.textContent = "学習EXP " + (journeyStatus.journey_exp || 0) + " ／ 通算 " + prog.cur;
    const lvL = document.getElementById("homeLvLabel");
    if (lvL) lvL.textContent = "Lv." + lv;
    const bar = document.getElementById("homeExpBar");
    if (bar) bar.style.width = prog.pct + "%";
    applyAppearance(
      document.getElementById("homeAvatarWrap"),
      document.getElementById("homeAvatarImg"),
      journeyStatus.appearance
    );
    renderGearPanel(journeyStatus.appearance, journeyStatus.inventory || []);
    renderEvolutionGrid(
      "homeEvoGrid",
      cls,
      (journeyStatus.appearance && journeyStatus.appearance.rank_id) || journeyStatus.rank_id || "novice",
      "homeEvoRankLabel"
    );
    const my = document.getElementById("myName");
    if (my) my.textContent = user;
  }

  function renderNextLesson() {
    const box = document.getElementById("nextLessonBox");
    if (!box) return;
    const les = journeyStatus.next_lesson;
    const boss = journeyStatus.next_boss;
    box.innerHTML = "";
    if (!les) {
      const p = document.createElement("p");
      p.className = "hint";
      p.style.margin = "0";
      p.textContent = boss
        ? "メインクエスト完了！ ボス戦か冒険録で復習しよう。"
        : "次のクエストを準備中… ワールドマップを確認しよう。";
      box.appendChild(p);
    } else {
      const left = document.createElement("div");
      left.innerHTML =
        "<strong>⚔ " +
        (les.title_ja || les.id) +
        '</strong><div class="hint">報酬 +' +
        (les.exp || 0) +
        " EXP ・ 教材クエスト</div>";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "出撃する";
      btn.onclick = () => openStudyLesson(les.id);
      box.appendChild(left);
      box.appendChild(btn);
    }
    if (boss) {
      const hint = document.createElement("div");
      hint.className = "next-boss-hint";
      hint.style.flexBasis = "100%";
      hint.textContent =
        "👹 週次/月次テスト出現：" +
        (boss.title_ja || boss.id) +
        "（ワールドのボス欄から受験。負けても学習進捗は消えない）";
      box.appendChild(hint);
    }
  }

  let currentStudyLessonId = null;
  let studyAutosaveTimer = null;
  let currentExamBossId = null;

  function setStudyTab(tab) {
    document.querySelectorAll("#studyTabs button").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-study-tab") === tab);
    });
    ["problem", "work", "guide", "ref"].forEach((name) => {
      const pane = document.getElementById(
        "studyPane" + name.charAt(0).toUpperCase() + name.slice(1)
      );
      if (pane) pane.classList.toggle("active", name === tab);
    });
  }

  function renderUnlockedGuides(guides) {
    const box = document.getElementById("studyGuideList");
    if (!box) return;
    box.innerHTML = "";
    (guides || []).forEach((g) => {
      const div = document.createElement("div");
      div.className = "study-guide-card";
      div.innerHTML =
        "<strong>" +
        (g.title_ja || "ガイド") +
        "</strong><p>" +
        (g.body_ja || "") +
        '</p><span class="src">' +
        (g.source_ja || "") +
        "</span>";
      box.appendChild(div);
    });
    if (!(guides || []).length) {
      box.innerHTML = '<p class="hint" style="margin:0">まだガイドは未開放です。「詰まったらガイドを見る」を押そう。</p>';
    }
  }

  async function saveStudyAnswerDraft() {
    if (!currentStudyLessonId) return;
    const ta = document.getElementById("studyAnswer");
    if (!ta) return;
    try {
      await api("/journey/lessons/" + encodeURIComponent(currentStudyLessonId) + "/attempt", {
        method: "POST",
        body: JSON.stringify({ answer: ta.value || "" }),
      });
    } catch (_e) {
      /* draft best-effort */
    }
  }

  async function openStudyLesson(lessonId) {
    try {
      const les =
        (journeyMap.lessons || []).find((x) => x.id === lessonId) ||
        (await api("/journey/lessons/" + encodeURIComponent(lessonId)));
      currentStudyLessonId = lessonId;
      document.getElementById("studyTitle").textContent = les.title_ja || lessonId;
      document.getElementById("studySummary").textContent = les.summary_ja || "";
      document.getElementById("studyExp").textContent =
        "目安 " +
        (les.estimated_minutes || 30) +
        "分 ・ +" +
        (les.exp || 0) +
        " 学習EXP";
      const goals = document.getElementById("studyGoals");
      goals.innerHTML = "";
      (les.goals_ja || []).forEach((g) => {
        const li = document.createElement("li");
        li.textContent = g;
        goals.appendChild(li);
      });
      const theory = document.getElementById("studyTheory");
      if (theory) {
        const paras = les.theory_ja || [];
        theory.innerHTML = paras.length
          ? paras.map((p) => "<p>" + p + "</p>").join("")
          : "<p>この単元の要点を下の実践で確認しよう。</p>";
      }
      const steps = document.getElementById("studySteps");
      steps.innerHTML = "";
      const practice = les.practice_steps && les.practice_steps.length ? les.practice_steps : les.steps || [];
      practice.forEach((s, i) => {
        const div = document.createElement("div");
        div.className = "study-step";
        div.innerHTML =
          "<strong>" +
          (i + 1) +
          ". " +
          (s.title_ja || "実践") +
          "</strong><p>" +
          (s.body_ja || "") +
          "</p>";
        steps.appendChild(div);
      });
      const checks = document.getElementById("studyChecklist");
      if (checks) {
        checks.innerHTML = "";
        (les.checklist_ja || []).forEach((c) => {
          const li = document.createElement("li");
          li.textContent = c;
          checks.appendChild(li);
        });
      }
      const res = document.getElementById("studyResources");
      res.innerHTML = "";
      const resources = les.resources || [];
      if (!resources.length) {
        res.innerHTML = '<p class="hint">参考リンクは準備中。まずは上のステップを実践しよう。</p>';
      } else {
        resources.forEach((r) => {
          const a = document.createElement("a");
          a.href = r.url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.textContent = (r.kind ? "[" + r.kind + "] " : "") + (r.title_ja || r.url);
          res.appendChild(a);
        });
      }
      document.getElementById("studyPractice").textContent = les.practice_ja || "";
      const enrich = document.getElementById("studyEnrich");
      if (les.detail_ja) {
        enrich.style.display = "block";
        enrich.textContent = "AI補足：" + les.detail_ja;
      } else {
        enrich.style.display = "none";
        enrich.textContent = "";
      }

      let attempt = null;
      try {
        attempt = await api("/journey/lessons/" + encodeURIComponent(lessonId) + "/attempt");
      } catch (_e) {
        attempt = null;
      }
      const study = (attempt && attempt.study) || {
        problem_ja: les.problem_ja || les.practice_ja || les.summary_ja || "",
        workspace_type: les.workspace_type || "text",
        method_guides: les.method_guides || [],
        min_answer_chars: les.min_answer_chars || 24,
      };
      const problemEl = document.getElementById("studyProblemText");
      if (problemEl) problemEl.textContent = study.problem_ja || "—";
      const ta = document.getElementById("studyAnswer");
      if (ta) {
        ta.value = (attempt && attempt.answer) || "";
        ta.classList.toggle("code-mode", study.workspace_type === "code");
        ta.placeholder =
          study.workspace_type === "code"
            ? "コードや手順を書いて提出しよう（実行ジャッジなし）"
            : "考えた手順・メモを書いて提出しよう";
      }
      const ansHint = document.getElementById("studyAnswerHint");
      if (ansHint) {
        ansHint.textContent =
          (study.min_answer_chars || 24) +
          "文字以上書いて提出するとスキルを獲得できます。詰まったらガイドへ。";
      }
      renderUnlockedGuides((attempt && attempt.unlocked_guides) || []);
      const hintMeta = document.getElementById("studyHintMeta");
      if (hintMeta) {
        const used = (attempt && attempt.hints_used) || 0;
        const total = (study.method_guides || []).length || 0;
        hintMeta.textContent =
          "ガイド開放 " + used + " / " + total + " — 教材・フォーラムの定石を段階的に表示します。";
      }
      const hintBtn = document.getElementById("studyHintBtn");
      if (hintBtn) hintBtn.disabled = !!les.completed;

      const doneBtn = document.getElementById("studyCompleteBtn");
      if (doneBtn) {
        doneBtn.style.display = les.completed ? "none" : "inline-block";
        doneBtn.disabled = !les.available;
        doneBtn.textContent = "提出してスキルを得る";
      }
      setStudyTab("problem");
      document.getElementById("studyModal").classList.add("open");
    } catch (e) {
      setErr(e.message);
    }
  }

  function closeStudyModal() {
    if (studyAutosaveTimer) {
      clearTimeout(studyAutosaveTimer);
      studyAutosaveTimer = null;
    }
    saveStudyAnswerDraft();
    document.getElementById("studyModal").classList.remove("open");
    currentStudyLessonId = null;
  }

  async function revealStudyHint() {
    if (!currentStudyLessonId) return;
    try {
      await saveStudyAnswerDraft();
      const res = await api("/journey/lessons/" + encodeURIComponent(currentStudyLessonId) + "/hint", {
        method: "POST",
        body: "{}",
      });
      renderUnlockedGuides(res.unlocked_guides || []);
      const hintMeta = document.getElementById("studyHintMeta");
      if (hintMeta) hintMeta.textContent = res.message_ja || "";
      setStudyTab("guide");
    } catch (e) {
      setErr(e.message);
    }
  }

  async function submitStudyLesson() {
    if (!currentStudyLessonId) return;
    const ta = document.getElementById("studyAnswer");
    const answer = ta ? ta.value || "" : "";
    try {
      const res = await api("/journey/lessons/" + encodeURIComponent(currentStudyLessonId) + "/submit", {
        method: "POST",
        body: JSON.stringify({ answer: answer }),
      });
      journeyStatus = res.status || journeyStatus;
      journeyMap = res.map || journeyMap;
      const chips = [];
      (res.skills_gained || []).forEach((s) => chips.push("スキル：" + (s.label_ja || s.id)));
      if (res.gear) chips.push("装備：" + (res.gear.label_ja || res.gear.item_id));
      if (res.rank) chips.push("進化：" + (res.rank.label_ja || res.rank.id));
      const warn =
        res.submit && res.submit.soft_check && res.submit.soft_check.warnings
          ? res.submit.soft_check.warnings
          : [];
      showRewardModal(
        "🎉 QUEST CLEAR!",
        [
          "EXP +" + (res.exp_gained || 0),
          (res.lesson && res.lesson.title_ja) || "",
          (res.submit && res.submit.message_ja) || "",
        ].concat(warn),
        chips
      );
      if (luna) luna.applyEmotion("cheer", 1500);
      closeStudyModal();
      applyJourneyUi();
      await refreshCore();
    } catch (e) {
      setErr(e.message);
      setStudyTab("work");
    }
  }

  async function openBossExam(bossId) {
    try {
      const exam = await api("/journey/bosses/" + encodeURIComponent(bossId) + "/exam");
      currentExamBossId = bossId;
      document.getElementById("examTitle").textContent =
        (exam.exam_label_ja || "確認テスト") + " — " + (exam.title_ja || bossId);
      document.getElementById("examSub").textContent =
        "これまでの学習を確認します。各問に短くても具体的に書いて提出しよう（失敗しても進捗は消えません）。";
      document.getElementById("examMsg").textContent = "";
      const box = document.getElementById("examQuestions");
      box.innerHTML = "";
      const saved = exam.answers || {};
      (exam.questions || []).forEach((q, i) => {
        const div = document.createElement("div");
        div.className = "exam-q";
        div.innerHTML =
          '<div class="q-lab">Q' +
          (i + 1) +
          "</div><p>" +
          (q.prompt_ja || "") +
          '</p><textarea data-qid="' +
          q.id +
          '" placeholder="解答を書く"></textarea>';
        const ta = div.querySelector("textarea");
        if (ta && saved[q.id]) ta.value = saved[q.id];
        box.appendChild(div);
      });
      const submitBtn = document.getElementById("examSubmitBtn");
      if (submitBtn) {
        submitBtn.disabled = !exam.available || !!exam.cleared;
        submitBtn.style.display = exam.cleared ? "none" : "inline-block";
      }
      document.getElementById("examModal").classList.add("open");
    } catch (e) {
      setErr(e.message);
    }
  }

  function closeExamModal() {
    document.getElementById("examModal").classList.remove("open");
    currentExamBossId = null;
  }

  async function submitBossExamAnswers() {
    if (!currentExamBossId) return;
    const answers = {};
    document.querySelectorAll("#examQuestions textarea[data-qid]").forEach((ta) => {
      answers[ta.getAttribute("data-qid")] = ta.value || "";
    });
    try {
      const res = await api("/journey/bosses/" + encodeURIComponent(currentExamBossId) + "/exam/submit", {
        method: "POST",
        body: JSON.stringify({ answers: answers }),
      });
      if (!res.success) {
        document.getElementById("examMsg").textContent = res.message_ja || "もう少し書き足して再挑戦しよう。";
        return;
      }
      if (res.status) journeyStatus = res.status;
      if (res.map) journeyMap = res.map;
      const chips = [];
      (res.skills_gained || []).forEach((s) => chips.push("スキル：" + (s.label_ja || s.id)));
      if (res.gear) chips.push("装備：" + (res.gear.label_ja || res.gear.item_id));
      showRewardModal(
        "🏆 " + (res.message_ja || "テストクリア！"),
        ["EXP +" + (res.exp_gained || 0), "score " + (res.score != null ? res.score : "")],
        chips
      );
      if (luna) luna.applyEmotion("cheer", 1500);
      closeExamModal();
      applyJourneyUi();
      await refreshCore();
    } catch (e) {
      setErr(e.message);
    }
  }

  function renderSkills() {
    const grid = document.getElementById("skillGrid");
    if (!grid) return;
    grid.innerHTML = "";
    const skills = journeyStatus.skills || [];
    if (!skills.length) {
      grid.innerHTML = '<p class="hint">レッスンをクリアするとスキルが増えます。</p>';
      return;
    }
    const colors = Object.values(SKILL_CLS);
    skills.forEach((s, i) => {
      const div = document.createElement("div");
      div.className = "skill";
      div.innerHTML =
        '<div class="icon" style="background:' +
        colors[i % colors.length] +
        '">' +
        (s.label_ja || s.id).slice(0, 1) +
        "</div><strong>" +
        (s.label_ja || s.id) +
        "</strong>";
      grid.appendChild(div);
    });
  }

  function showRewardModal(title, lines, chips) {
    const modal = document.getElementById("rewardModal");
    document.getElementById("rewardTitle").textContent = title;
    document.getElementById("rewardBody").innerHTML = (lines || []).map((x) => "<p>" + x + "</p>").join("");
    const chipEl = document.getElementById("rewardChips");
    chipEl.innerHTML = (chips || []).map((c) => '<span class="chip-mini">' + c + "</span>").join("");
    modal.classList.add("open");
  }

  async function completeJourneyLesson(lessonId) {
    try {
      const res = await api("/journey/lessons/" + encodeURIComponent(lessonId) + "/complete", {
        method: "POST",
        body: "{}",
      });
      journeyStatus = res.status || journeyStatus;
      journeyMap = res.map || journeyMap;
      const chips = [];
      (res.skills_gained || []).forEach((s) => chips.push("スキル：" + (s.label_ja || s.id)));
      if (res.gear) chips.push("装備：" + (res.gear.label_ja || res.gear.item_id));
      if (res.rank) chips.push("進化：" + (res.rank.label_ja || res.rank.id));
      showRewardModal("🎉 QUEST CLEAR!", ["EXP +" + (res.exp_gained || 0), (res.lesson && res.lesson.title_ja) || ""], chips);
      if (luna) luna.applyEmotion("cheer", 1500);
      applyJourneyUi();
      await refreshCore();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function enrichLesson(lessonId) {
    try {
      const res = await api("/journey/lessons/" + encodeURIComponent(lessonId) + "/enrich", {
        method: "POST",
        body: "{}",
      });
      alert(res.detail_ja || "詳細を追加しました。");
      await loadJourney();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function challengeBoss(bossId, success) {
    try {
      const res = await api("/journey/bosses/" + encodeURIComponent(bossId) + "/challenge", {
        method: "POST",
        body: JSON.stringify({ success: !!success }),
      });
      if (res.status) journeyStatus = res.status;
      if (res.map) journeyMap = res.map;
      const chips = [];
      (res.skills_gained || []).forEach((s) => chips.push("スキル：" + (s.label_ja || s.id)));
      if (res.gear) chips.push("装備：" + (res.gear.label_ja || res.gear.item_id));
      showRewardModal(res.success ? "🏆 BOSS DEFEATED!" : "退却… また挑もう", [res.message_ja || ""], chips);
      if (res.success && luna) luna.applyEmotion("cheer", 1500);
      applyJourneyUi();
      await refreshCore();
    } catch (e) {
      setErr(e.message);
    }
  }

  function renderMapDailyQuest() {
    const box = document.getElementById("mapQuestList");
    if (!box) return;
    const les = journeyStatus.next_lesson;
    if (!les) {
      box.innerHTML = '<p class="hint" style="margin:0">次の学習単元はホームタブで確認できます。</p>';
      return;
    }
    box.innerHTML =
      '<div style="font-size:.74rem;font-weight:800">⚔ ' +
      (les.title_ja || les.id) +
      '</div><div class="hint">報酬 +' +
      (les.exp || 0) +
      " EXP ・ 出撃可能</div>";
  }

  function renderMap() {
    const path = document.getElementById("mapPath");
    if (!path) return;
    path.innerHTML = "";
    const list = (journeyMap.stages || []).length
      ? journeyMap.stages
      : regions.length
        ? regions
        : [{ label_ja: "始まりの平原", unlocked: true, current: true }];
    const pts = [];
    list.forEach((r, i) => {
      const pos = MAP_POSITIONS[i] || MAP_POSITIONS[MAP_POSITIONS.length - 1];
      const left = parseFloat(pos.left) || 12;
      const top = parseFloat(pos.top) || 55;
      pts.push({ x: left, y: top });
      const node = document.createElement("div");
      const bossHere = (journeyMap.bosses || []).some((b) => b.stage_id === r.id && !b.cleared);
      node.className =
        "map-node" +
        (r.current ? " current" : "") +
        (!r.unlocked ? " locked" : "") +
        (r.cleared ? " cleared" : "") +
        (bossHere ? " boss" : "");
      node.style.left = pos.left;
      node.style.top = pos.top;
      const icon = bossHere ? "👹" : r.cleared ? "⚑" : r.current ? "★" : !r.unlocked ? "🔒" : "◆";
      node.innerHTML =
        '<span class="flag">' +
        icon +
        "</span>" +
        (r.label_ja || r.id) +
        (r.progress ? '<div class="hint" style="color:#fff;opacity:.9">' + r.progress + "</div>" : "");
      path.appendChild(node);
    });
    const svg = document.getElementById("mapRouteSvg");
    if (svg && pts.length > 1) {
      let d = "M " + pts[0].x + " " + pts[0].y;
      for (let i = 1; i < pts.length; i++) {
        const prev = pts[i - 1];
        const cur = pts[i];
        const mx = (prev.x + cur.x) / 2;
        d += " Q " + mx + " " + (prev.y - 8) + " " + cur.x + " " + cur.y;
      }
      svg.innerHTML = '<path d="' + d + '" />';
    } else if (svg) {
      svg.innerHTML = "";
    }
    const cur = list.find((r) => r.current) || list[0];
    const curIdx = Math.max(0, list.indexOf(cur));
    const lbl = document.getElementById("mapRegionLabel");
    if (lbl) {
      lbl.textContent =
        "現在：" +
        (cur ? cur.label_ja : "始まりの平原") +
        (journeyStatus.career_title_ja ? "（" + journeyStatus.career_title_ja + "）" : "");
    }
    const hud = document.getElementById("mapHudRegion");
    if (hud) hud.textContent = lbl ? lbl.textContent : "現在：始まりの平原";
    const hudExp = document.getElementById("mapHudExp");
    if (hudExp) hudExp.textContent = "学習EXP " + (journeyStatus.journey_exp || 0);
    const mapAv = document.getElementById("mapAvatar");
    const mapAvImg = document.getElementById("mapAvatarImg");
    if (mapAv && mapAvImg && cur) {
      const pos = MAP_POSITIONS[curIdx] || MAP_POSITIONS[MAP_POSITIONS.length - 1];
      mapAv.hidden = false;
      mapAv.classList.add("alive");
      mapAv.style.left = pos.left;
      mapAv.style.top = pos.top;
      const ap = journeyStatus.appearance || {};
      let src =
        ap.evolution_sprite ||
        evolutionSpritePath(journeyStatus.class_id || selectedClass, journeyStatus.rank_id || "novice");
      if (src && src.indexOf("_stand.png") < 0 && /\/static\/rpg\/characters\/[^/]+\.png$/.test(src)) {
        src = src.replace(/\.png$/, "_stand.png");
      }
      mapAvImg.src = src;
    }
  }

  function renderLessons() {
    const list = document.getElementById("questList");
    if (!list) return;
    list.innerHTML = "";
    const lessons = (journeyMap.lessons || []).filter((l) => (l.boss_type || "none") === "none");
    if (!lessons.length) {
      list.innerHTML = '<p class="hint">進路を選ぶとレッスンが表示されます。</p>';
      return;
    }
    lessons.forEach((les) => {
      const row = document.createElement("div");
      row.className = "lesson-row" + (les.completed ? " done" : "");
      const detail = les.detail_ja
        ? '<div class="hint">' + les.detail_ja.slice(0, 80) + (les.detail_ja.length > 80 ? "…" : "") + "</div>"
        : "";
      row.innerHTML =
        "<div><strong>" +
        (les.title_ja || les.id) +
        '</strong><div class="hint">+' +
        (les.exp || 0) +
        " EXP" +
        (les.completed ? " ・完了" : les.available ? "" : " ・ロック") +
        "</div>" +
        detail +
        '</div><div class="actions"></div>';
      const actions = row.querySelector(".actions");
      const enrichBtn = document.createElement("button");
      enrichBtn.type = "button";
      enrichBtn.className = "ghost";
      enrichBtn.textContent = "情報";
      enrichBtn.onclick = () => enrichLesson(les.id);
      actions.appendChild(enrichBtn);
      if (!les.completed && les.available) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "出撃";
        btn.onclick = () => openStudyLesson(les.id);
        actions.appendChild(btn);
      }
      list.appendChild(row);
    });
  }

  function renderBosses() {
    const list = document.getElementById("bossList");
    if (!list) return;
    list.innerHTML = "";
    const bosses = journeyMap.bosses || [];
    if (!bosses.length) {
      list.innerHTML = '<p class="hint">ボスはマップ進行で解放されます。</p>';
      return;
    }
    bosses.forEach((b) => {
      const row = document.createElement("div");
      row.className = "boss-row";
      const kind =
        b.boss_type === "weekly"
          ? "週次テスト"
          : b.boss_type === "monthly"
            ? "月次テスト"
            : b.boss_type === "career_final"
              ? "最終試験"
              : BOSS_LABEL[b.boss_type] || b.boss_type;
      row.innerHTML =
        "<div><strong>" +
        (b.title_ja || b.id) +
        '</strong><div class="hint">' +
        kind +
        " ・ " +
        (b.cleared ? "クリア済" : b.available ? "受験可" : b.requirement_ja || "ロック") +
        '</div></div><div class="actions"></div>';
      const actions = row.querySelector(".actions");
      if (!b.cleared && b.available) {
        const exam = document.createElement("button");
        exam.type = "button";
        exam.textContent = "受験する";
        exam.onclick = () => openBossExam(b.id);
        const lose = document.createElement("button");
        lose.type = "button";
        lose.className = "ghost";
        lose.textContent = "退却";
        lose.onclick = () => challengeBoss(b.id, false);
        actions.appendChild(exam);
        actions.appendChild(lose);
      }
      list.appendChild(row);
    });
  }

  function renderCareerPortfolio() {
    const cls = journeyStatus.class_id || selectedClass;
    const rankId = journeyStatus.rank_id || "novice";
    const ap = journeyStatus.appearance || {};
    const lv = journeyStatus.level || stateData.level || 1;
    const exp = journeyStatus.total_exp || stateData.total_exp || 0;
    const prog = expProgress(exp, lv);
    const pAv = document.getElementById("portfolioAvatarImg");
    if (pAv) pAv.src = ap.evolution_sprite || evolutionSpritePath(cls, rankId);
    const pTitle = document.getElementById("portfolioTitle");
    if (pTitle) pTitle.textContent = (stateData.user_display_name || "学習者") + " Lv." + lv;
    const pSub = document.getElementById("portfolioSub");
    if (pSub) {
      pSub.textContent =
        (journeyStatus.class_ja || classLabel(cls)) +
        " ／ " +
        (journeyStatus.rank_ja || "見習い") +
        (journeyStatus.career_title_ja ? " ・ " + journeyStatus.career_title_ja : "");
    }
    const pBar = document.getElementById("portfolioExpBar");
    if (pBar) pBar.style.width = prog.pct + "%";
    const pStory = document.getElementById("portfolioStory");
    if (pStory) {
      pStory.textContent = journeyStatus.selected
        ? (journeyStatus.career_title_ja || "進路") +
          "への冒険。習熟「" +
          (journeyStatus.rank_ja || "見習い") +
          "」— レッスン " +
          (journeyStatus.completed_count || 0) +
          " 完了。理論と実践を重ね、最終ボスへ向かおう。"
        : "クラスと職業を選ぶと、冒険の記録がここに表示されます。";
    }
    const row = document.getElementById("portfolioStats");
    if (row) {
      row.innerHTML =
        '<div class="stat-box" style="background:linear-gradient(135deg,#c9a227,#8b6914)"><span>レッスン</span><strong>' +
        (journeyStatus.completed_count || 0) +
        '</strong></div><div class="stat-box" style="background:linear-gradient(135deg,#497cff,#31d2ff)"><span>装備</span><strong>' +
        ((journeyStatus.inventory || []).length || 0) +
        '</strong></div><div class="stat-box" style="background:linear-gradient(135deg,#7a5cff,#b47aff)"><span>ボス</span><strong>' +
        ((journeyStatus.boss_clears || []).length || 0) +
        "</strong></div>";
    }
    const route = document.getElementById("routeList");
    if (route) {
      if (!journeyStatus.selected) {
        route.innerHTML = '<p class="hint">まだ進路を選んでいません。</p>';
      } else {
        route.innerHTML =
          "<p><strong>" +
          (journeyStatus.career_title_ja || "") +
          '</strong></p><p class="hint">クラス：' +
          (journeyStatus.class_ja || "") +
          " ／ 進化：" +
          (journeyStatus.rank_ja || "") +
          '</p><div style="margin-top:.4rem">' +
          (journeyStatus.skills || [])
            .map((s) => '<span class="chip-mini">' + (s.label_ja || s.id) + "</span>")
            .join("") +
          "</div>";
      }
    }
    const gear = document.getElementById("gearList");
    if (gear) {
      const inv = journeyStatus.inventory || [];
      if (!inv.length) gear.innerHTML = '<p class="hint">レッスン報酬で装備が増えます。</p>';
      else {
        gear.innerHTML = inv
          .map((g) => '<span class="chip-mini">' + (g.label_ja || g.id) + "（" + (g.slot || "") + "）</span>")
          .join("");
      }
    }
    const story = document.getElementById("storyBox");
    if (story) {
      story.textContent = journeyStatus.selected
        ? (journeyStatus.career_title_ja || "進路") +
          "への旅。ランク「" +
          (journeyStatus.rank_ja || "見習い") +
          "」。レッスンを重ねて最終ボスへ挑もう。"
        : "クラスと職業を選んで旅を始めよう。";
    }
  }

  function stopLunaSpeech() {
    if (lunaAudio) {
      try {
        lunaAudio.onended = null;
        lunaAudio.onerror = null;
        lunaAudio.pause();
      } catch (_) {}
      lunaAudio = null;
    }
    if (lunaAudioUrl) {
      URL.revokeObjectURL(lunaAudioUrl);
      lunaAudioUrl = null;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (luna && !luna.thinking) luna.stopLipSync();
  }

  function unlockAudio() {
    if (audioUnlocked) return;
    audioUnlocked = true;
    try {
      if (window.speechSynthesis) {
        const warm = new SpeechSynthesisUtterance(" ");
        warm.volume = 0;
        window.speechSynthesis.speak(warm);
        window.speechSynthesis.cancel();
      }
    } catch (_) {}
    try {
      const silent = new Audio(
        "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA="
      );
      silent.volume = 0.01;
      silent.play().catch(() => {});
    } catch (_) {}
  }

  function ensureVoicesLoaded() {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) {
        resolve([]);
        return;
      }
      const have = window.speechSynthesis.getVoices() || [];
      if (have.length) {
        voicesReady = true;
        resolve(have);
        return;
      }
      const done = () => {
        voicesReady = true;
        resolve(window.speechSynthesis.getVoices() || []);
      };
      window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
      setTimeout(done, 600);
    });
  }

  function pickJaBrowserVoice(voices) {
    const list = voices || (window.speechSynthesis && window.speechSynthesis.getVoices()) || [];
    const prefer = ["Nanami", "Haruka", "Kyoko", "Google 日本語", "Microsoft Ayumi", "Ichiro"];
    for (const name of prefer) {
      const hit = list.find((v) => (v.name || "").includes(name));
      if (hit) return hit;
    }
    return list.find((v) => (v.lang || "").toLowerCase().startsWith("ja")) || null;
  }

  async function speakJaBrowserFallback(text) {
    if (!window.speechSynthesis) return;
    unlockAudio();
    window.speechSynthesis.cancel();
    const voices = await ensureVoicesLoaded();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ja-JP";
    u.rate = 1.05;
    const voice = pickJaBrowserVoice(voices);
    if (voice) u.voice = voice;
    u.onstart = () => {
      if (luna) luna.startLipSync();
    };
    u.onend = () => {
      if (luna) luna.stopLipSync();
    };
    u.onerror = () => {
      if (luna) luna.stopLipSync();
    };
    window.speechSynthesis.speak(u);
  }

  async function speakJa(text) {
    const line = (text || "").trim();
    if (!voiceOn || !line) return;
    const mySeq = ++speakSeq;
    unlockAudio();
    stopLunaSpeech();
    // Chat path: browser voice only (instant). Gemini TTS competes with chat
    // quota/latency — keep it opt-in via localStorage luna_gemini_voice=1.
    const wantGemini = localStorage.getItem("luna_gemini_voice") === "1" && ttsFailStreak < 3;
    await speakJaBrowserFallback(line);
    if (!wantGemini || mySeq !== speakSeq) return;

    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 8000) : null;
    try {
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = "Bearer " + token;
      const res = await fetch("/tts/speak", {
        method: "POST",
        headers,
        body: JSON.stringify({ text: line }),
        signal: ctrl ? ctrl.signal : undefined,
      });
      if (!res.ok) throw new Error("tts");
      const blob = await res.blob();
      if (mySeq !== speakSeq) return;
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      lunaAudioUrl = URL.createObjectURL(blob);
      lunaAudio = new Audio(lunaAudioUrl);
      lunaAudio.onplay = () => {
        if (luna) luna.startLipSync();
      };
      lunaAudio.onended = () => {
        if (mySeq === speakSeq && luna) luna.stopLipSync();
      };
      lunaAudio.onerror = () => {
        if (mySeq === speakSeq) speakJaBrowserFallback(line).catch(() => {});
      };
      await lunaAudio.play();
      ttsFailStreak = 0;
    } catch (_) {
      ttsFailStreak += 1;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function syncVoiceBtn() {
    const btn = document.getElementById("voiceBtn");
    if (!btn) return;
    btn.title = voiceOn ? "音声ON" : "音声OFF";
    btn.style.opacity = voiceOn ? "1" : ".55";
    try {
      localStorage.setItem("luna_voice", voiceOn ? "1" : "0");
    } catch (_) {}
  }

  const DEFAULT_CHIPS = [
    "体調を相談したい",
    "お金の相談",
    "予定を整理したい",
    "健康に追記したい",
    "欲しいものがある",
  ];

  function chipRouteForLabel(label) {
    const t = String(label || "");
    if (t.includes("健康に追記")) return { type: "subview", name: "health" };
    if (t.includes("予定を整理")) return { type: "subview", name: "schedule" };
    if (t.includes("欲しいもの")) return { type: "subview", name: "goals" };
    // Consult chips: open the module first, then also chat
    if (t.includes("体調を相談") || (t.includes("体調") && t.includes("相談"))) {
      return { type: "consult", name: "health" };
    }
    if (t.includes("お金の相談") || (t.includes("お金") && t.includes("相談"))) {
      return { type: "consult", name: "money" };
    }
    if (t.includes("自分で") || t.includes("自由")) return { type: "focus" };
    return { type: "chat" };
  }

  function renderChips(list) {
    const chipsEl = document.getElementById("chips");
    if (!chipsEl) return;
    chipsEl.innerHTML = "";
    const labels = list && list.length ? list : DEFAULT_CHIPS;
    labels.forEach((label) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = label;
      b.onclick = async () => {
        const route = chipRouteForLabel(label);
        if (route.type === "focus") {
          document.getElementById("message").focus();
          return;
        }
        if (route.type === "subview") {
          openSubview(route.name);
          setNavActive("luna");
          return;
        }
        if (route.type === "consult") {
          // Stay on home chat so the conversation is visible; open module if chat fails
          closeAllSubviews();
          setNavActive("luna");
          const ok = await sendMessage(label);
          if (!ok) {
            openSubview(route.name);
            setNavActive(route.name === "money" || route.name === "health" ? route.name : "luna");
          }
          return;
        }
        sendMessage(label);
      };
      chipsEl.appendChild(b);
    });
  }

  function applyChat(data) {
    const dialogueEl = document.getElementById("dialogue");
    const line = ((data && data.dialogue) || "").trim();
    try {
      if (luna) luna.stopThinking();
    } catch (_) {}
    if (dialogueEl && line) dialogueEl.textContent = line;
    renderChips((data && data.suggested_replies) || DEFAULT_CHIPS);
    const emo = data && data.game_state && data.game_state.emotion;
    try {
      if (luna && line) {
        if (emo) luna.applyEmotion(emo);
        else luna.reactToText(line, { greeting: firstChat, fallback: "happy", force: true });
      }
    } catch (_) {}
    firstChat = false;
    if (line) speakJa(line).catch(() => {});
    // Defer heavy refresh so chat feels instant
    setTimeout(() => {
      refreshCore().catch(() => {});
    }, 400);
  }

  function showLocalGreeting() {
    const dialogueEl = document.getElementById("dialogue");
    const cur = (dialogueEl && dialogueEl.textContent) || "";
    if (!dialogueEl) return;
    if (cur && cur !== "…" && cur !== "...") return;
    dialogueEl.textContent = "こんにちは。LUNAです。今日も一緒にがんばろうね。";
    renderChips(DEFAULT_CHIPS);
    try {
      if (luna) luna.reactToText(dialogueEl.textContent, { greeting: true, fallback: "happy", force: true });
    } catch (_) {}
  }

  function paintNow() {
    return new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    });
  }

  async function sendMessage(text) {
    const msg = (text || "").trim();
    if (!msg || busy) return false;
    busy = true;
    unlockAudio();
    // Instant think reaction BEFORE any network wait
    try {
      if (luna) luna.startThinking();
    } catch (_) {}
    await paintNow();
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) sendBtn.disabled = true;
    setErr("");
    const msgEl = document.getElementById("message");
    if (msgEl) msgEl.value = "";
    try {
      if (!chatStarted) chatStarted = true;
      const data = await api("/chat", { method: "POST", body: JSON.stringify({ message: msg }) });
      applyChat(data);
      return true;
    } catch (e) {
      try {
        if (luna) luna.stopThinking();
      } catch (_) {}
      const soft = "うまく返事できなかったみたい。もう一度送ってくれる？";
      const dialogueEl = document.getElementById("dialogue");
      if (dialogueEl) dialogueEl.textContent = soft;
      setErr(e.message || String(e));
      try {
        if (luna) luna.reactToText(soft, { fallback: "sad", force: true });
      } catch (_) {}
      speakJa(soft).catch(() => {});
      return false;
    } finally {
      busy = false;
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  async function startChat() {
    if (chatStarted) return;
    chatStarted = true;
    showLocalGreeting();
    renderChips(DEFAULT_CHIPS);
    try {
      const data = await api("/chat/start", { method: "POST", body: JSON.stringify({ message: "" }) });
      applyChat(data);
    } catch (e) {
      setErr(e.message);
      // Keep local greeting + default chips; allow retry on next luna tab focus.
      chatStarted = false;
      showLocalGreeting();
      renderChips(DEFAULT_CHIPS);
    }
  }

  function renderThemePicker() {
    const cur = LunaTheme.currentTheme();
    ["themeGrid", "themeGridMenu"].forEach((id) => {
      const grid = document.getElementById(id);
      if (!grid) return;
      grid.innerHTML = "";
      Object.values(LunaTheme.THEMES).forEach((t) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "theme-btn" + (t.id === cur ? " active" : "");
        const sw = t.swatch || ["#ccc", "#999", "#666"];
        b.innerHTML =
          '<span class="theme-swatch" style="--sw0:' +
          sw[0] +
          ";--sw1:" +
          sw[1] +
          ";--sw2:" +
          sw[2] +
          '"></span><span>' +
          t.label +
          "</span>";
        b.onclick = () => {
          LunaTheme.applyTheme(t.id);
          renderThemePicker();
        };
        grid.appendChild(b);
      });
    });
  }

  async function loadScheduleView(opts) {
    const preserveCursor = !!(opts && opts.preserveCursor);
    const skipHome = !!(opts && opts.skipHome);
    try {
      const focus = selectedDate || document.getElementById("addDate")?.value || todayIso();
      const data = await api("/schedule/events?date=" + encodeURIComponent(focus));
      allScheduleEvents = data.events || [];
      datesWithEvents = new Set(data.dates_with_events || []);
      window.__lastExtendPrompt = data.extend_prompt || null;
      showExtendHorizonPrompt(data.extend_prompt);
      if (!selectedDate) selectedDate = focus || data.today || todayIso();
      if (!preserveCursor) {
        const parts = selectedDate.split("-").map(Number);
        calCursor = new Date(parts[0], parts[1] - 1, 1);
      }
      document.getElementById("addDate").value = selectedDate;
      renderCalendar();
      renderDayEvents();
      if (!skipHome) await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  function renderCalendar() {
    const y = calCursor.getFullYear();
    const m = calCursor.getMonth();
    const label = document.getElementById("calMonthLabel");
    if (label) label.textContent = y + "年" + (m + 1) + "月";
    const grid = document.getElementById("calGrid");
    if (!grid) return;
    grid.innerHTML = "";
    const first = new Date(y, m, 1);
    const startPad = first.getDay();
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const today = todayIso();
    for (let i = 0; i < startPad; i++) {
      const blank = document.createElement("button");
      blank.type = "button";
      blank.className = "cal-day muted";
      blank.disabled = true;
      blank.textContent = "";
      grid.appendChild(blank);
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = isoFromYmd(y, m, d);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cal-day";
      if (iso === today) btn.classList.add("today");
      if (iso === selectedDate) btn.classList.add("selected");
      if (datesWithEvents.has(iso)) btn.classList.add("has-event");
      btn.textContent = String(d);
      btn.onclick = () => selectCalendarDay(iso);
      grid.appendChild(btn);
    }
  }

  function renderDayEvents() {
    const title = document.getElementById("dayPanelTitle");
    if (title) title.textContent = fmtDateJa(selectedDate);
    const el = document.getElementById("dayEventList");
    if (!el) return;
    const items = eventsForDate(selectedDate);
    el.innerHTML = "";
    if (!items.length) {
      el.innerHTML = '<p class="hint">この日の予定はまだありません。「＋」で追加できます。</p>';
      return;
    }
    items.forEach((ev) => {
      const row = document.createElement("div");
      row.className = "todo-row" + (ev.done ? " done" : "");
      const time = ev.time || ev.end_time ? formatTimeRange(ev) + " · " : "";
      const recur = ev.recurrence
        ? '<span class="recur-tag">🔁同じ' + weekdayJaFromIso(ev.date || selectedDate) + "曜</span>"
        : "";
      row.innerHTML = '<span style="flex:1">' + time + ev.title + recur + "</span>";
      const acts = document.createElement("div");
      acts.className = "acts";
      const doneBtn = document.createElement("button");
      doneBtn.textContent = ev.done ? "戻す" : "完了";
      doneBtn.onclick = () => toggleEventDone(ev.id, !ev.done);
      const editBtn = document.createElement("button");
      editBtn.textContent = "編集";
      editBtn.onclick = () => openEditEvent(ev);
      const delBtn = document.createElement("button");
      delBtn.textContent = "削除";
      delBtn.className = "danger";
      delBtn.onclick = () => deleteScheduleEvent(ev.id);
      acts.appendChild(doneBtn);
      acts.appendChild(editBtn);
      acts.appendChild(delBtn);
      row.appendChild(acts);
      el.appendChild(row);
    });
  }

  function resetAddForm(keepDate) {
    document.getElementById("editEventId").value = "";
    document.getElementById("editRecurrenceId").value = "";
    document.getElementById("addTitle").value = "";
    document.getElementById("addTime").value = "";
    document.getElementById("addEndTime").value = "";
    document.getElementById("addNote").value = "";
    document.getElementById("addDate").value = keepDate || selectedDate || todayIso();
    document.getElementById("addSaveBtn").textContent = "保存";
    document.getElementById("addForm").classList.remove("open");
  }

  async function deleteScheduleEvent(id) {
    if (!id) return;
    const ev = (allScheduleEvents || []).find((e) => e.id === id);
    const isRecurring = !!(ev && (ev.recurrence_id || ev.recurrence || String(id).startsWith("rec-")));
    if (!confirm("この予定を削除しますか？")) return;
    let scope = "this";
    if (isRecurring) {
      scope = confirm(
        "同じ曜日のこれから先の予定もすべて削除しますか？\n\nOK = すべて削除\nキャンセル = この日だけ"
      )
        ? "all"
        : "this";
    }
    try {
      await api("/schedule/events/" + id + "?scope=" + encodeURIComponent(scope), { method: "DELETE" });
      resetAddForm(selectedDate || todayIso());
      await loadScheduleView();
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function loadMoneyView() {
    try {
      const d = await api("/life/money/dashboard");
      renderMoneyDashboard(d);
    } catch (e) {
      setErr(e.message);
    }
  }

  async function loadHealthView() {
    try {
      const d = await api("/life/health/dashboard");
      renderHealthDashboard(d);
    } catch (e) {
      setErr(e.message);
    }
  }

  function eventsForDate(iso) {
    return allScheduleEvents
      .filter((e) => e.date === iso)
      .sort((a, b) => (a.time || "99:99").localeCompare(b.time || "99:99"));
  }

  function updateMentalReminderBanner(s) {
    const banner = document.getElementById("mentalRemindBanner");
    if (!banner) return;
    const show = !!(s && (s.health?.mental_reminder || (s.pending_notification && String(s.pending_notification).includes("気分"))));
    banner.classList.toggle("open", show && !sessionStorage.getItem("mentalModalOpen"));
    const txt = document.getElementById("mentalRemindText");
    if (txt) txt.textContent = s.pending_notification || "LUNAが今日の気分を聞きたいよ";
  }

  function formatTimeRange(ev) {
    if (!ev) return "終日";
    const start = ev.time || "";
    const end = ev.end_time || "";
    if (start && end) return start + "〜" + end;
    if (start) return start + "〜";
    if (end) return "〜" + end;
    return "終日";
  }

  function attachSwipeDelete(row, onDelete) {
    let startX = 0;
    let tracking = false;
    let locked = false;
    row.addEventListener(
      "touchstart",
      (e) => {
        startX = e.touches[0].clientX;
        tracking = true;
      },
      { passive: true }
    );
    row.addEventListener("touchend", (e) => {
      if (!tracking) return;
      const dx = e.changedTouches[0].clientX - startX;
      tracking = false;
      // swipe left -> delete (per-item)
      if (dx < -48 && !locked) {
        locked = true;
        try {
          onDelete && onDelete();
        } finally {
          setTimeout(() => {
            locked = false;
          }, 900);
        }
      }
    });
  }

  function renderHomeToday(items) {
    const el = document.getElementById("homeTodayList");
    if (!el) return;
    el.innerHTML = "";
    if (!items.length) {
      el.innerHTML = '<p class="hint">まだ予定はありません。カレンダーから追加できます。</p>';
      return;
    }
    items.forEach((ev) => {
      const row = document.createElement("div");
      row.className = "home-today-item" + (ev.done ? " done" : "");
      row.innerHTML =
        '<span class="t">' +
        formatTimeRange(ev) +
        "</span><span style='flex:1'>" +
        ev.title +
        "</span>";
      // swipe left to delete (no delete button)
      attachSwipeDelete(row, () => deleteScheduleEvent(ev.id));
      el.appendChild(row);
    });
  }

  function isoFromYmd(y, m0, d) {
    return y + "-" + String(m0 + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
  }

  function clampDayInMonth(y, m0, day) {
    const max = new Date(y, m0 + 1, 0).getDate();
    return Math.min(Math.max(1, day || 1), max);
  }

  function shiftCalendarMonth(delta) {
    const prevDay = selectedDate ? Number(selectedDate.split("-")[2]) : 1;
    const next = new Date(calCursor.getFullYear(), calCursor.getMonth() + delta, 1);
    calCursor = next;
    const y = next.getFullYear();
    const m0 = next.getMonth();
    const today = todayIso();
    const monthPrefix = y + "-" + String(m0 + 1).padStart(2, "0");
    // Keep month grid and day panel in lockstep — this was the desync bug.
    const nextIso = today.startsWith(monthPrefix)
      ? today
      : isoFromYmd(y, m0, clampDayInMonth(y, m0, prevDay));
    selectedDate = nextIso;
    const dateInput = document.getElementById("addDate");
    if (dateInput) dateInput.value = nextIso;
    renderCalendar();
    renderDayEvents();
    // Refresh expansion around the browsed month (skip home summary — keeps UI snappy).
    loadScheduleView({ preserveCursor: true, skipHome: true });
  }

  function selectCalendarDay(iso) {
    selectedDate = iso;
    const parts = iso.split("-").map(Number);
    calCursor = new Date(parts[0], parts[1] - 1, 1);
    const dateInput = document.getElementById("addDate");
    if (dateInput) dateInput.value = iso;
    renderCalendar();
    renderDayEvents();
  }

  function openEditEvent(ev) {
    document.getElementById("editEventId").value = ev.id || "";
    document.getElementById("editRecurrenceId").value = ev.recurrence_id || "";
    document.getElementById("addTitle").value = ev.title || "";
    document.getElementById("addDate").value = ev.date || selectedDate;
    document.getElementById("addTime").value = ev.time || "";
    document.getElementById("addEndTime").value = ev.end_time || "";
    document.getElementById("addNote").value = ev.note || "";
    document.getElementById("addForm").classList.add("open");
    document.getElementById("addSaveBtn").textContent = "更新";
  }

  async function toggleEventDone(id, done) {
    try {
      await api("/schedule/events/" + id + "/complete", {
        method: "POST",
        body: JSON.stringify({ done }),
      });
      await loadScheduleView();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function addScheduleEvent() {
    const editId = document.getElementById("editEventId").value;
    const title = document.getElementById("addTitle").value.trim();
    const date = document.getElementById("addDate").value;
    const time = (document.getElementById("addTime").value || "").trim();
    const endTime = (document.getElementById("addEndTime").value || "").trim();
    const note = document.getElementById("addNote").value.trim();
    if (!title || !date) return;
    // Accept both `8:00` and `08:00`, but normalize to `HH:MM` before saving.
    const TIME_RE = /^(\d{1,2}):([0-5]\d)$/;
    function normalizeTime(t) {
      const m = TIME_RE.exec(t);
      if (!m) return null;
      const h = Number(m[1]);
      if (h < 0 || h > 23) return null;
      return String(h).padStart(2, "0") + ":" + m[2];
    }
    const normTime = time ? normalizeTime(time) : null;
    if (time && !normTime) {
      setErr("開始時刻はHH:MM（24h）で入力してください。");
      return;
    }
    const normEndTime = endTime ? normalizeTime(endTime) : null;
    if (endTime && !normEndTime) {
      setErr("終了時刻はHH:MM（24h）で入力してください。");
      return;
    }
    try {
      if (editId) {
        const recurrenceId = document.getElementById("editRecurrenceId").value;
        const isRecurring = !!(recurrenceId || String(editId).startsWith("rec-"));
        let scope = "this";
        if (isRecurring) {
          const editAll = confirm(
            "繰り返し予定です。\n\n同じ曜日のこれから先の予定もすべて変更しますか？\n\nOK = すべて変更\nキャンセル = この日だけ変更"
          );
          scope = editAll ? "all" : "this";
        }
        await api("/schedule/events/" + editId, {
          method: "PATCH",
          body: JSON.stringify({
            title,
            date,
            time: normTime || null,
            end_time: normEndTime || null,
            note: note || null,
            scope,
          }),
        });
        selectedDate = date;
        resetAddForm(date);
        await loadScheduleView();
      } else {
        // Simple rule: ask once — repeat on the same weekday forever, or this day only.
        const recurrence = askRepeatSameWeekday(date) ? "weekly" : null;
        await api("/schedule/events", {
          method: "POST",
          body: JSON.stringify({
            title,
            date,
            time: normTime || null,
            end_time: normEndTime || null,
            note: note || null,
            recurrence,
          }),
        });
        selectedDate = date;
        resetAddForm(date);
        await loadScheduleView();
      }
    } catch (e) {
      setErr(e.message);
    }
  }

  function setHealthFormErr(msg) {
    const el = document.getElementById("healthFormErr");
    if (el) el.textContent = msg || "";
    if (msg) setErr(msg);
    else setErr("");
  }

  function renderHealthDashboard(d) {
    if (!d) return;
    document.getElementById("healthScoreBig").textContent = d.score ?? "—";
    document.getElementById("healthStatus").textContent = d.status_ja || "—";
    document.getElementById("healthMessage").textContent = d.message_ja || "";
    const bmiLine = document.getElementById("healthBmiLine");
    if (bmiLine) {
      const bits = [];
      if (d.bmi) bits.push("BMI " + d.bmi);
      if (d.bmi_range_ja) bits.push(d.bmi_range_ja);
      bmiLine.textContent = bits.length ? bits.join(" · ") : "BMI —（年齢・身長・体重を入力）";
    }
    const list = document.getElementById("healthBreakdown");
    if (list) {
      list.innerHTML = "";
      (d.breakdown || []).forEach((row) => {
        const li = document.createElement("li");
        li.innerHTML =
          '<span class="k">' +
          (row.label_ja || row.key) +
          '</span><span class="n">' +
          (row.note || "") +
          '</span><span class="v">' +
          (row.score ?? "—") +
          "</span>";
        list.appendChild(li);
      });
    }
    renderSuggestList("healthGoalSuggest", d.goal_suggestions);
    renderSuggestList("healthExerciseSuggest", d.exercise_suggestions);
    const p = d.profile || {};
    setInputVal("editAge", p.age);
    setInputVal("editWeight", p.weight_kg);
    setInputVal("editHeight", p.height_cm);
    setInputVal("editTargetWeight", p.target_weight_kg);
    setInputVal("editTargetHeight", p.target_height_cm);
    setInputVal("editSleepHours", p.sleep_hours);
    setInputVal("editWakeTime", p.wake_time);
    setInputVal("editBedtime", p.bedtime);
    setInputVal("editHobbies", p.hobbies);
    setInputVal("editSchoolHours", p.school_hours);
    setInputVal("editStudyHours", p.study_hours);
    setInputVal("editRelaxHours", p.relax_hours);
    setInputVal("editExercisePlan", p.exercise_plan);
  }

  async function saveHealthMetrics() {
    const TIME_RE = /^(\d{1,2}):([0-5]\d)$/;
    function normalizeTime(t) {
      if (!t) return null;
      const raw = String(t).trim();
      // Allow 24:00 as end-of-day bedtime → 00:00
      if (raw === "24:00") return "00:00";
      const m = TIME_RE.exec(raw);
      if (!m) return null;
      const h = Number(m[1]);
      if (h > 23) return null;
      return String(h).padStart(2, "0") + ":" + m[2];
    }
    setHealthFormErr("");
    const wakeRaw = strOrNull("editWakeTime");
    const bedRaw = strOrNull("editBedtime");
    const wake = normalizeTime(wakeRaw);
    const bed = normalizeTime(bedRaw);
    if (wakeRaw && !wake) {
      setHealthFormErr("起床は HH:MM（例 07:15）で入力してください");
      return;
    }
    if (bedRaw && !bed) {
      setHealthFormErr("就寝は HH:MM（例 23:00 / 24:00）で入力してください");
      return;
    }
    const sleepRaw = (document.getElementById("editSleepHours")?.value || "").trim();
    if (sleepRaw && numOrNull("editSleepHours") == null) {
      setHealthFormErr("睡眠時間は数字で入力してください（例 7.5 または 7,5）");
      return;
    }
    try {
      const res = await api("/life/health/profile", {
        method: "PATCH",
        body: JSON.stringify({
          age: numOrNull("editAge"),
          weight_kg: numOrNull("editWeight"),
          height_cm: numOrNull("editHeight"),
          target_weight_kg: numOrNull("editTargetWeight"),
          target_height_cm: numOrNull("editTargetHeight"),
          sleep_hours: numOrNull("editSleepHours"),
          wake_time: wake,
          bedtime: bed,
          hobbies: strOrNull("editHobbies"),
          school_hours: numOrNull("editSchoolHours"),
          study_hours: numOrNull("editStudyHours"),
          relax_hours: numOrNull("editRelaxHours"),
          exercise_plan: strOrNull("editExercisePlan"),
        }),
      });
      renderHealthDashboard(res.dashboard || res);
      setHealthFormErr("");
      const healthView = document.getElementById("sub-health");
      if (healthView) healthView.scrollTo({ top: 0, behavior: "smooth" });
      const savedHint = document.getElementById("healthSavedHint");
      if (savedHint) {
        savedHint.textContent = "保存しました。上の評価を確認してね。";
        savedHint.classList.add("show");
        setTimeout(() => savedHint.classList.remove("show"), 3500);
      }
      await loadHomeSummary();
    } catch (e) {
      setHealthFormErr(e.message);
    }
  }

  function showMentalModal(choices) {
    const overlay = document.getElementById("mentalOverlay");
    const box = document.getElementById("mentalChoices");
    if (!overlay || !box) return;
    box.innerHTML = "";
    (choices || ["元気", "普通", "疲れ", "落ち込み", "不安"]).forEach((label) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.onclick = () => submitMentalStatus(label);
      box.appendChild(btn);
    });
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    sessionStorage.setItem("mentalModalOpen", "1");
  }

  function hideMentalModal() {
    const overlay = document.getElementById("mentalOverlay");
    if (!overlay) return;
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    sessionStorage.removeItem("mentalModalOpen");
  }

  async function submitMentalStatus(status) {
    try {
      const res = await api("/life/health/mental", {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      hideMentalModal();
      mentalSkippedSession = false;
      const banner = document.getElementById("mentalRemindBanner");
      if (banner) banner.classList.remove("open");
      if (res.dashboard) renderHealthDashboard(res.dashboard);
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function checkMentalCheckin(opts) {
    const force = !!(opts && opts.force);
    try {
      const st = await api("/life/health/mental/status");
      if (st.needed && (force || !mentalSkippedSession)) {
        showMentalModal(st.choices);
      } else if (st.reminder || st.needed) {
        updateMentalReminderBanner({
          health: { mental_reminder: !!st.reminder || !!st.needed },
          pending_notification: st.pending_notification || "LUNAが今日の気分を聞きたいよ",
        });
      } else {
        const banner = document.getElementById("mentalRemindBanner");
        if (banner) banner.classList.remove("open");
      }
    } catch (_) {}
  }

  function setMoneyFormErr(msg) {
    const el = document.getElementById("moneyFormErr");
    if (el) el.textContent = msg || "";
    if (msg) setErr(msg);
    else setErr("");
  }

  function renderMoneyFundInputs(funds, profile) {
    const box = document.getElementById("moneyFundInputs");
    if (!box) return;
    box.innerHTML = "";
    (funds || []).forEach((f) => {
      const wrap = document.createElement("div");
      wrap.className = "money-fund";
      const curId = "editFund_" + f.key + "_current";
      const tgtId = "editFund_" + f.key + "_target";
      const curVal = profile && profile[f.key + "_current"] != null ? profile[f.key + "_current"] : f.current;
      const tgtVal = profile && profile[f.key + "_target"] != null ? profile[f.key + "_target"] : f.target;
      wrap.innerHTML =
        '<div class="top"><span class="name">' +
        (f.label_ja || f.key) +
        '</span><span class="hint">' +
        (f.hint_ja || "") +
        "</span></div>" +
        '<div class="money-fund-inputs">' +
        "<div><label>いま（円）</label><input id=\"" +
        curId +
        '" type="number" min="0" step="1000" /></div>' +
        "<div><label>目標（円）</label><input id=\"" +
        tgtId +
        '" type="number" min="0" step="1000" /></div>' +
        "</div>";
      box.appendChild(wrap);
      setInputVal(curId, curVal);
      setInputVal(tgtId, tgtVal);
    });
  }

  function renderMoneyDashboard(d) {
    if (!d) return;
    const scoreEl = document.getElementById("moneyScoreBig");
    if (scoreEl) scoreEl.textContent = d.score ?? "—";
    const st = document.getElementById("moneyStatus");
    if (st) st.textContent = d.status_ja || "—";
    const ageLine = document.getElementById("moneyAgeLine");
    if (ageLine) ageLine.textContent = d.age_label_ja || "—";
    const roomLine = document.getElementById("moneyRoomLine");
    if (roomLine) roomLine.textContent = d.room_note_ja || "—";
    const msg = document.getElementById("moneyMessage");
    if (msg) msg.textContent = d.message_ja || "";
    const rule = document.getElementById("moneyRuleLine");
    if (rule) rule.textContent = d.rule_ja || "";
    renderSuggestList("moneyTips", d.tips_ja || []);

    const todayLine = document.getElementById("moneyTodaySpentLine");
    if (todayLine) {
      todayLine.textContent =
        "今日 " +
        fmtYen(d.today_spent || 0) +
        " ／ 目安 " +
        fmtYen(d.daily_budget || 0) +
        "/日";
    }
    const paceLine = document.getElementById("moneyPaceLine");
    if (paceLine) {
      paceLine.textContent =
        "今月累計 " +
        fmtYen(d.month_spent || 0) +
        " ／ 残り予算 " +
        fmtYen(d.remaining_budget || 0) +
        "（残り" +
        (d.days_left ?? "—") +
        "日・目安 " +
        fmtYen(d.recommended_daily || 0) +
        "/日）";
    }
    const paceWarn = document.getElementById("moneyPaceWarn");
    if (paceWarn) {
      paceWarn.textContent = d.pace_warning_ja || "";
      paceWarn.classList.remove("warn", "info");
      if (d.pace_level === "warn") paceWarn.classList.add("warn", "pace-warn");
      else if (d.pace_level === "info") paceWarn.classList.add("info", "pace-warn");
      else paceWarn.classList.add("pace-warn");
    }

    const bars = document.getElementById("moneyFundsBars");
    if (bars) {
      bars.innerHTML = "";
      (d.funds || []).forEach((f) => {
        const row = document.createElement("div");
        row.className = "money-fund";
        row.innerHTML =
          '<div class="top"><span class="name">' +
          (f.label_ja || f.key) +
          '</span><span class="pct">' +
          (f.pct ?? 0) +
          "%</span></div>" +
          '<div class="bar"><span style="width:' +
          (f.pct ?? 0) +
          '%"></span></div>' +
          '<div class="meta">' +
          fmtYen(f.current) +
          " / " +
          fmtYen(f.target) +
          "</div>";
        bars.appendChild(row);
      });
    }

    const p = d.profile || {};
    setInputVal("editMoneyIncome", p.monthly_income != null ? p.monthly_income : d.monthly_income);
    setInputVal("editMoneyExpense", p.monthly_expense != null ? p.monthly_expense : d.monthly_expense);
    setInputVal("editPurchaseName", p.purchase_name || d.purchase_name || "");
    renderMoneyFundInputs(d.funds || [], p);
  }

  async function addTodaySpend() {
    const err = document.getElementById("spendFormErr");
    if (err) err.textContent = "";
    const amount = numOrNull("editTodaySpend");
    if (amount == null || amount <= 0) {
      if (err) err.textContent = "金額を入力してね";
      return;
    }
    try {
      const res = await api("/life/money/spend", {
        method: "POST",
        body: JSON.stringify({
          amount: Math.round(amount),
          note: strOrNull("editTodaySpendNote") || "",
        }),
      });
      renderMoneyDashboard(res.dashboard || res);
      setInputVal("editTodaySpend", "");
      setInputVal("editTodaySpendNote", "");
      const hint = document.getElementById("moneySavedHint");
      if (hint) {
        hint.textContent = "今日の支出を記録したよ";
        hint.classList.add("show");
        setTimeout(() => hint.classList.remove("show"), 2200);
      }
    } catch (e) {
      if (err) err.textContent = (e && e.message) || "記録に失敗しました";
    }
  }

  async function loadGoalsView() {
    try {
      const d = await api("/life/goals/dashboard");
      renderGoalsDashboard(d);
    } catch (e) {
      const box = document.getElementById("goalsList");
      if (box) box.innerHTML = '<p class="hint">読み込みに失敗しました</p>';
    }
  }

  function renderGoalsDashboard(d) {
    const sum = document.getElementById("goalsSummaryLine");
    if (sum) sum.textContent = d.label || "目標なし";
    const list = document.getElementById("goalsList");
    if (!list) return;
    const items = d.items || [];
    if (!items.length) {
      list.innerHTML = '<p class="hint">まだ目標がありません。下から追加してね。</p>';
      return;
    }
    list.innerHTML = "";
    items.forEach((g) => {
      const row = document.createElement("div");
      row.className = "goal-row";
      const unit = g.unit || "";
      row.innerHTML =
        '<div class="top"><span class="name"></span><span class="pct">' +
        (g.pct ?? 0) +
        "%</span></div>" +
        '<div class="bar"><span style="width:' +
        (g.pct ?? 0) +
        '%"></span></div>' +
        '<div class="meta"></div>' +
        '<div class="acts">' +
        '<button type="button" data-act="prog">進捗を更新</button>' +
        '<button type="button" data-act="del" class="danger">削除</button>' +
        "</div>";
      row.querySelector(".name").textContent = g.title || "目標";
      row.querySelector(".meta").textContent =
        String(g.current ?? 0) + unit + " / " + String(g.target ?? 0) + unit + (g.note ? " · " + g.note : "");
      row.querySelector('[data-act="prog"]').onclick = () => updateGoalProgress(g);
      row.querySelector('[data-act="del"]').onclick = () => removeGoal(g.id);
      list.appendChild(row);
    });
  }

  async function addGoalFromForm() {
    const err = document.getElementById("goalsFormErr");
    if (err) err.textContent = "";
    const title = strOrNull("goalTitle");
    if (!title) {
      if (err) err.textContent = "タイトルを入力してね";
      return;
    }
    try {
      const res = await api("/life/goals", {
        method: "POST",
        body: JSON.stringify({
          title,
          current: numOrNull("goalCurrent") || 0,
          target: numOrNull("goalTarget") || 0,
          unit: strOrNull("goalUnit") || "円",
          note: strOrNull("goalNote") || "",
        }),
      });
      renderGoalsDashboard(res.dashboard || res);
      setInputVal("goalTitle", "");
      setInputVal("goalCurrent", "0");
      setInputVal("goalTarget", "");
      setInputVal("goalNote", "");
      const hint = document.getElementById("goalsSavedHint");
      if (hint) {
        hint.textContent = "目標を追加したよ";
        hint.classList.add("show");
        setTimeout(() => hint.classList.remove("show"), 2200);
      }
      refreshHomeStatus().catch(() => {});
    } catch (e) {
      if (err) err.textContent = (e && e.message) || "追加に失敗しました";
    }
  }

  async function updateGoalProgress(g) {
    const raw = prompt(
      "現在の進捗（" + (g.unit || "") + "）",
      String(g.current != null ? g.current : 0)
    );
    if (raw == null) return;
    const n = Number(String(raw).replace(/,/g, ""));
    if (!Number.isFinite(n) || n < 0) {
      alert("数値を入力してね");
      return;
    }
    try {
      const res = await api("/life/goals/" + encodeURIComponent(g.id), {
        method: "PATCH",
        body: JSON.stringify({ current: n }),
      });
      renderGoalsDashboard(res.dashboard || res);
      refreshHomeStatus().catch(() => {});
    } catch (e) {
      alert((e && e.message) || "更新に失敗しました");
    }
  }

  async function removeGoal(id) {
    if (!confirm("この目標を削除しますか？")) return;
    try {
      const res = await api("/life/goals/" + encodeURIComponent(id), { method: "DELETE" });
      renderGoalsDashboard(res.dashboard || res);
      refreshHomeStatus().catch(() => {});
    } catch (e) {
      alert((e && e.message) || "削除に失敗しました");
    }
  }

  function refreshHomeStatus() {
    return loadHomeSummary();
  }

  async function saveMoneyMetrics() {
    setMoneyFormErr("");
    const payload = {
      monthly_income: numOrNull("editMoneyIncome"),
      monthly_expense: numOrNull("editMoneyExpense"),
      purchase_name: strOrNull("editPurchaseName"),
    };
    ["purchase", "emergency", "reserve", "invest"].forEach((key) => {
      const curEl = document.getElementById("editFund_" + key + "_current");
      const tgtEl = document.getElementById("editFund_" + key + "_target");
      if (curEl) payload[key + "_current"] = numOrNull("editFund_" + key + "_current");
      if (tgtEl) payload[key + "_target"] = numOrNull("editFund_" + key + "_target");
    });
    try {
      const res = await api("/life/money/profile", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      renderMoneyDashboard(res.dashboard || res);
      setMoneyFormErr("");
      const moneyView = document.getElementById("sub-money");
      if (moneyView) moneyView.scrollTo({ top: 0, behavior: "smooth" });
      const hint = document.getElementById("moneySavedHint");
      if (hint) {
        hint.textContent = "保存しました。上の評価を確認してね。";
        hint.classList.add("show");
        setTimeout(() => hint.classList.remove("show"), 3500);
      }
      await loadHomeSummary();
    } catch (e) {
      setMoneyFormErr(e.message);
    }
  }

  async function loadHomeSummary() {
    try {
      const s = await api("/home/summary");
      document.getElementById("homeDate").textContent = s.date_ja || "";
      document.getElementById("stSchedule").textContent = s.schedule?.label || "予定なし";
      document.getElementById("stHealth").textContent = s.health?.label || "良好";
      const stMoney = document.getElementById("stMoney");
      if (stMoney) stMoney.textContent = s.money?.label || "—";
      document.getElementById("stGoals").textContent = s.goals?.label || "—";
      renderHomeToday(s.schedule?.today_items || []);
      updateMentalReminderBanner(s);
    } catch (_) {}
  }

  function numOrNull(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const t = (el.value || "").trim().replace(",", ".");
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }

  function renderSuggestList(elId, items) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = "";
    const list = items || [];
    if (!list.length) {
      el.classList.add("empty");
      el.innerHTML = "<li>プロフィールを保存すると提案が出ます。</li>";
      return;
    }
    el.classList.remove("empty");
    list.forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      el.appendChild(li);
    });
  }

  function setInputVal(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = val == null || val === "" ? "" : val;
  }

  function strOrNull(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const t = (el.value || "").trim();
    return t || null;
  }

  function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.onclick = () => switchTab(btn.dataset.nav);
    });
    document.querySelectorAll(".fsq-sub").forEach((btn) => {
      btn.onclick = () => switchFsqSub(btn.dataset.fsq);
    });
    document.querySelectorAll("[data-open]").forEach((el) => {
      el.onclick = () => {
        const name = el.dataset.open;
        if (name === "health" || name === "money" || name === "goals") switchTab(name);
        else {
          setNavActive("luna");
          openSubview(name);
        }
      };
    });
    document.querySelectorAll("[data-back]").forEach((el) => {
      el.onclick = () => {
        closeAllSubviews();
        setNavActive("luna");
        switchTab("luna");
      };
    });
    document.querySelectorAll("[data-ask]").forEach((el) => {
      el.onclick = async () => {
        closeAllSubviews();
        switchTab("luna");
        await sendMessage(el.dataset.ask);
      };
    });
    document.getElementById("settingsBtn").onclick = () => {
      renderThemePicker();
      setLunaView("settings");
    };
    document.getElementById("settingsBack").onclick = () => setLunaView("main");
    const menuThemeBtn = document.getElementById("menuThemeBtn");
    const menuSettings = document.getElementById("menuSettings");
    if (menuThemeBtn && menuSettings) {
      menuThemeBtn.onclick = () => {
        const open = menuSettings.style.display !== "block";
        menuSettings.style.display = open ? "block" : "none";
        if (open) renderThemePicker();
      };
    }
    document.getElementById("toggleAddBtn").onclick = () => {
      resetAddForm(selectedDate || todayIso());
      document.getElementById("addForm").classList.add("open");
    };
    document.getElementById("addCancelBtn").onclick = () => resetAddForm(selectedDate || todayIso());
    document.getElementById("addSaveBtn").onclick = () => addScheduleEvent();
    const extendYes = document.getElementById("extendHorizonYes");
    const extendNo = document.getElementById("extendHorizonNo");
    if (extendYes) extendYes.onclick = () => extendRecurringHorizons();
    if (extendNo) extendNo.onclick = () => dismissExtendHorizonPrompt();
    document.getElementById("calPrev").onclick = () => shiftCalendarMonth(-1);
    document.getElementById("calNext").onclick = () => shiftCalendarMonth(1);
    const saveHealthBtn = document.getElementById("saveHealthBtn");
    if (saveHealthBtn) saveHealthBtn.onclick = () => saveHealthMetrics();
    const mentalSkip = document.getElementById("mentalSkipBtn");
    if (mentalSkip) {
      mentalSkip.onclick = () => {
        mentalSkippedSession = true;
        hideMentalModal();
        updateMentalReminderBanner({
          health: { mental_reminder: true },
          pending_notification: "LUNAが今日の気分を聞きたいよ",
        });
      };
    }
    const mentalRemindBtn = document.getElementById("mentalRemindBtn");
    if (mentalRemindBtn) {
      mentalRemindBtn.onclick = () => {
        mentalSkippedSession = false;
        checkMentalCheckin({ force: true });
      };
    }
    const saveMoneyBtn = document.getElementById("saveMoneyBtn");
    if (saveMoneyBtn) saveMoneyBtn.onclick = () => saveMoneyMetrics();
    const addSpendBtn = document.getElementById("addSpendBtn");
    if (addSpendBtn) addSpendBtn.onclick = () => addTodaySpend();
    const addGoalBtn = document.getElementById("addGoalBtn");
    if (addGoalBtn) addGoalBtn.onclick = () => addGoalFromForm();
    document.getElementById("sendBtn").onclick = () => sendMessage(document.getElementById("message").value);
    document.getElementById("message").onkeydown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage(document.getElementById("message").value);
      }
    };
    document.getElementById("morningBtn").onclick = async () => {
      try {
        const goal = prompt("今日の目標は？", "") || "";
        await api("/checkin/morning", { method: "POST", body: JSON.stringify({ goal }) });
        switchTab("luna");
        await sendMessage(goal ? "今日の目標は「" + goal + "」。朝チェックインお願いします。" : "朝チェックインお願いします。");
      } catch (e) {
        setErr(e.message);
      }
    };
    document.getElementById("eveningBtn").onclick = async () => {
      try {
        await api("/checkin/evening", { method: "POST", body: JSON.stringify({}) });
        switchTab("luna");
        await sendMessage("夜チェックインお願いします。");
      } catch (e) {
        setErr(e.message);
      }
    };
    document.getElementById("voiceBtn").onclick = () => {
      unlockAudio();
      voiceOn = !voiceOn;
      syncVoiceBtn();
      if (!voiceOn) stopLunaSpeech();
      else {
        ttsFailStreak = 0;
        const sample = (document.getElementById("dialogue") || {}).textContent || "こんにちは。";
        if (sample && sample !== "…" && sample !== "...") speakJa(sample).catch(() => {});
      }
    };
    document.getElementById("refreshCareerBtn").onclick = () => loadJourney().catch((e) => setErr(e.message));
    const backClass = document.getElementById("backToClassBtn");
    if (backClass) {
      backClass.onclick = () => {
        onboardStep = "class";
        applyJourneyUi();
      };
    }
    const resetJ = document.getElementById("resetJourneyBtn");
    if (resetJ) {
      resetJ.onclick = () => {
        if (!confirm("クラスと職業を選び直しますか？（進行はリセットされます）")) return;
        reselectJourney = true;
        onboardStep = "class";
        applyJourneyUi();
      };
    }
    const rewardClose = document.getElementById("rewardCloseBtn");
    if (rewardClose) {
      rewardClose.onclick = () => document.getElementById("rewardModal").classList.remove("open");
    }
    const studyClose = document.getElementById("studyCloseBtn");
    if (studyClose) studyClose.onclick = () => closeStudyModal();
    const studyComplete = document.getElementById("studyCompleteBtn");
    if (studyComplete) studyComplete.onclick = () => submitStudyLesson();
    const studyHintBtn = document.getElementById("studyHintBtn");
    if (studyHintBtn) studyHintBtn.onclick = () => revealStudyHint();
    document.querySelectorAll("#studyTabs button").forEach((btn) => {
      btn.onclick = () => setStudyTab(btn.getAttribute("data-study-tab") || "problem");
    });
    const studyAnswer = document.getElementById("studyAnswer");
    if (studyAnswer) {
      studyAnswer.addEventListener("input", () => {
        if (studyAutosaveTimer) clearTimeout(studyAutosaveTimer);
        studyAutosaveTimer = setTimeout(() => saveStudyAnswerDraft(), 900);
      });
    }
    const examSubmit = document.getElementById("examSubmitBtn");
    if (examSubmit) examSubmit.onclick = () => submitBossExamAnswers();
    const examRetreat = document.getElementById("examRetreatBtn");
    if (examRetreat) {
      examRetreat.onclick = async () => {
        const id = currentExamBossId;
        closeExamModal();
        if (id) await challengeBoss(id, false);
      };
    }
    const studyEnrichBtn = document.getElementById("studyEnrichBtn");
    if (studyEnrichBtn) {
      studyEnrichBtn.onclick = async () => {
        if (!currentStudyLessonId) return;
        await enrichLesson(currentStudyLessonId);
        await openStudyLesson(currentStudyLessonId);
      };
    }
    document.getElementById("logoutBtn").onclick = () => {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    };
    const mini = document.getElementById("lunaStage");
    if (mini) mini.onclick = () => luna && luna.onTap && luna.onTap();
  }

  async function refreshCore() {
    try {
      const [state, rpg, tax, brain, jst] = await Promise.all([
        api("/state/me"),
        api("/rpg/me"),
        api("/career/taxonomy"),
        api("/brain/me"),
        api("/journey/status").catch(() => null),
      ]);
      stateData = {
        level: state.current_level || rpg.level || 1,
        total_exp: state.total_exp || rpg.total_exp || 0,
        companion_name: state.companion_name,
        user_display_name: state.user_display_name,
      };
      rpgData = rpg.rpg || {};
      regions = rpg.regions || [];
      window._careerClusters = tax.career_clusters || [];
      (tax.rpg_classes || []).forEach((c) => {
        classLabels[c.id] = c.label_ja;
      });
      if (jst) {
        journeyStatus = jst;
        if (jst.class_id) selectedClass = jst.class_id;
      } else if (rpgData.class_id) {
        selectedClass = rpgData.class_id;
      }
      const modePill = document.getElementById("modePill");
      if (modePill) modePill.textContent = brain.mode || "—";
      if (currentTab === "fsq") await loadJourney();
      else renderHomeHeader();
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function boot() {
    if (!LunaAuth.requireLogin("/app")) return;
    token = LunaAuth.getToken();
    syncVoiceBtn();
    bindEvents();
    ensureVoicesLoaded().catch(() => {});
    document.addEventListener(
      "pointerdown",
      () => {
        unlockAudio();
      },
      { once: true, passive: true }
    );
    try {
      const me = await api("/auth/me");
      if (me.is_admin) document.getElementById("adminLink").classList.remove("hidden");
      luna = new LunaAvatar(document.getElementById("lunaSprite"), null, document.getElementById("lunaStage"));
      // Speak-first: greet immediately, refresh other panels in parallel.
      showLocalGreeting();
      const greetP = startChat();
      const coreP = refreshCore();
      await greetP;
      await coreP;
      await loadHomeSummary();
      await checkMentalCheckin();
    } catch (_) {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    }
  }

  boot();
})();
