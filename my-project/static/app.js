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
  }

  function closeSubview(name) {
    const el = document.getElementById("sub-" + name);
    if (el) el.classList.add("hidden");
  }

  function closeAllSubviews() {
    ["schedule", "health", "money"].forEach(closeSubview);
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
    if (name === "health" || name === "money") {
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
    return "/static/rpg/characters/" + cls + "_" + rank + ".svg";
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

  function applyAppearance(wrap, img, appearance) {
    if (!wrap || !img) return;
    const ap = appearance || {};
    wrap.className = "hero-avatar " + (ap.css_classes || "");
    const classId = ap.class_id || journeyStatus.class_id || selectedClass;
    const rankId = ap.rank_id || journeyStatus.rank_id || "novice";
    const evo = ap.evolution_sprite || ap.sprite || (classId ? evolutionSpritePath(classId, rankId) : null);
    if (evo && classId) {
      wrap.classList.add("has-evolution");
      img.src = evo;
      img.alt = (ap.class_label_ja || classLabel(classId)) + " " + (ap.rank_label_ja || journeyStatus.rank_ja || "");
    } else if (ap.sprite) {
      img.src = ap.sprite;
    }
    const tag = document.getElementById("homeAvatarClass");
    if (tag) tag.textContent = ap.class_label_ja || classLabel(ap.class_id) || "—";
    const emblem = document.getElementById("homeAvatarEmblem");
    if (emblem) emblem.textContent = ap.class_emblem_ja || (ap.class_label_ja || "旅")[0] || "旅";
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
    panel.innerHTML = slots
      .map((slot) => {
        const row = bySlot[slot];
        const label = row ? row.label_ja || row.id || "装備中" : "未装備";
        return (
          '<div class="gear-slot"><span class="k">' +
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
    const badge = document.getElementById("homeClassBadge");
    if (badge) {
      badge.textContent =
        "クラス：" +
        (journeyStatus.class_ja || classLabel(cls)) +
        " ／ 習熟：" +
        (journeyStatus.rank_ja || "見習い");
    }
    const role = document.getElementById("homeRoleName");
    if (role) role.textContent = journeyStatus.career_title_ja || user;
    const desc = document.getElementById("homeRoleDesc");
    if (desc) {
      desc.textContent = journeyStatus.selected
        ? "職業学習 " +
          done +
          " 単元完了。理論→実践の長い道のりを積み上げよう。"
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
        ? "いまの単元は一段落。マップの確認テスト（ボス）か、進路タブで復習しよう。"
        : "次の学習単元を準備中、またはマップを確認しよう。";
      box.appendChild(p);
    } else {
      const left = document.createElement("div");
      left.innerHTML =
        "<strong>" +
        (les.title_ja || les.id) +
        '</strong><div class="hint">+' +
        (les.exp || 0) +
        " EXP ・ 教材あり</div>";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "開く";
      btn.onclick = () => openStudyLesson(les.id);
      box.appendChild(left);
      box.appendChild(btn);
    }
    if (boss) {
      const hint = document.createElement("div");
      hint.className = "next-boss-hint";
      hint.style.flexBasis = "100%";
      hint.textContent =
        "ボス解放中：" +
        (boss.title_ja || boss.id) +
        "（マップのボス欄から挑戦。負けても学習進捗は消えない）";
      box.appendChild(hint);
    }
  }

  let currentStudyLessonId = null;

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
      const doneBtn = document.getElementById("studyCompleteBtn");
      if (doneBtn) {
        doneBtn.style.display = les.completed ? "none" : "inline-block";
        doneBtn.disabled = !(les.available || les.completed === false);
        if (!les.available) doneBtn.disabled = true;
        if (les.available) doneBtn.disabled = false;
      }
      document.getElementById("studyModal").classList.add("open");
    } catch (e) {
      setErr(e.message);
    }
  }

  function closeStudyModal() {
    document.getElementById("studyModal").classList.remove("open");
    currentStudyLessonId = null;
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
      showRewardModal("学習を記録した！", ["EXP +" + (res.exp_gained || 0), (res.lesson && res.lesson.title_ja) || ""], chips);
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
      showRewardModal(res.success ? "ボス討伐！" : "退却…", [res.message_ja || ""], chips);
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
      '<div style="font-size:.74rem;font-weight:800">' +
      (les.title_ja || les.id) +
      '</div><div class="hint">+' +
      (les.exp || 0) +
      " EXP ・ 教材あり</div>";
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
    list.forEach((r, i) => {
      const pos = MAP_POSITIONS[i] || MAP_POSITIONS[MAP_POSITIONS.length - 1];
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
      node.innerHTML =
        '<div class="dot"></div>' +
        (r.label_ja || r.id) +
        (r.progress ? '<div class="hint" style="color:#fff;opacity:.85">' + r.progress + "</div>" : "");
      path.appendChild(node);
    });
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
      mapAv.style.left = pos.left;
      mapAv.style.top = pos.top;
      const ap = journeyStatus.appearance || {};
      mapAvImg.src =
        ap.evolution_sprite ||
        evolutionSpritePath(journeyStatus.class_id || selectedClass, journeyStatus.rank_id || "novice");
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
      enrichBtn.textContent = "詳しく";
      enrichBtn.onclick = () => enrichLesson(les.id);
      actions.appendChild(enrichBtn);
      if (!les.completed && les.available) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "開く";
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
      row.innerHTML =
        "<div><strong>" +
        (b.title_ja || b.id) +
        '</strong><div class="hint">' +
        (BOSS_LABEL[b.boss_type] || b.boss_type) +
        " ・ " +
        (b.cleared ? "討伐済" : b.available ? "挑戦可" : b.requirement_ja || "ロック") +
        '</div></div><div class="actions"></div>';
      const actions = row.querySelector(".actions");
      if (!b.cleared && b.available) {
        const win = document.createElement("button");
        win.type = "button";
        win.textContent = "挑戦";
        win.onclick = () => challengeBoss(b.id, true);
        const lose = document.createElement("button");
        lose.type = "button";
        lose.className = "ghost";
        lose.textContent = "退却";
        lose.onclick = () => challengeBoss(b.id, false);
        actions.appendChild(win);
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
      lunaAudio.pause();
      lunaAudio = null;
    }
    if (lunaAudioUrl) {
      URL.revokeObjectURL(lunaAudioUrl);
      lunaAudioUrl = null;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (luna) luna.stopLipSync();
  }

  function pickJaBrowserVoice() {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    const prefer = ["Nanami", "Haruka", "Kyoko", "Google 日本語", "Microsoft Ayumi"];
    for (const name of prefer) {
      const hit = voices.find((v) => v.name.includes(name));
      if (hit) return hit;
    }
    return voices.find((v) => (v.lang || "").toLowerCase().startsWith("ja")) || null;
  }

  function speakJaBrowserFallback(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ja-JP";
    const voice = pickJaBrowserVoice();
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
    stopLunaSpeech();
    // After repeated Gemini TTS failures, keep chat snappy with browser voice
    // without removing the Gemini narrator path.
    if (ttsFailStreak >= 2) {
      speakJaBrowserFallback(line);
      return;
    }
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 10000) : null;
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
      lunaAudioUrl = URL.createObjectURL(blob);
      lunaAudio = new Audio(lunaAudioUrl);
      lunaAudio.onplay = () => {
        if (luna) luna.startLipSync();
      };
      lunaAudio.onended = () => {
        if (mySeq === speakSeq) stopLunaSpeech();
      };
      lunaAudio.onerror = () => {
        if (mySeq === speakSeq) stopLunaSpeech();
      };
      await lunaAudio.play();
      ttsFailStreak = 0;
    } catch (_) {
      ttsFailStreak += 1;
      if (mySeq === speakSeq) speakJaBrowserFallback(line);
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

  function renderChips(list) {
    const chipsEl = document.getElementById("chips");
    chipsEl.innerHTML = "";
    (list || []).forEach((label) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = label;
      b.onclick = () => {
        if (label.includes("自分で") || label.includes("自由")) {
          document.getElementById("message").focus();
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
    if (dialogueEl && line) dialogueEl.textContent = line;
    renderChips((data && data.suggested_replies) || []);
    const emo = data && data.game_state && data.game_state.emotion;
    try {
      if (luna && line) {
        if (emo) luna.applyEmotion(emo);
        else luna.reactToText(line, { greeting: firstChat, fallback: "happy" });
      }
    } catch (_) {}
    firstChat = false;
    // Voice + core refresh must not block chat replies / busy lock.
    if (line) speakJa(line).catch(() => {});
    refreshCore().catch((e) => setErr(e.message || String(e)));
  }

  function showLocalGreeting() {
    const dialogueEl = document.getElementById("dialogue");
    const cur = (dialogueEl && dialogueEl.textContent) || "";
    if (!dialogueEl) return;
    if (cur && cur !== "…" && cur !== "..." && cur !== "考え中…") return;
    dialogueEl.textContent = "こんにちは。LUNAです。今日も一緒にがんばろうね。";
    try {
      if (luna) luna.reactToText(dialogueEl.textContent, { greeting: true, fallback: "happy" });
    } catch (_) {}
  }

  async function sendMessage(text) {
    const msg = (text || "").trim();
    if (!msg || busy) return;
    busy = true;
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) sendBtn.disabled = true;
    setErr("");
    const msgEl = document.getElementById("message");
    if (msgEl) msgEl.value = "";
    const dialogueEl = document.getElementById("dialogue");
    if (dialogueEl) dialogueEl.textContent = "考え中…";
    try {
      if (luna) luna.reactToText(msg, { fallback: "think" });
    } catch (_) {}
    try {
      if (!chatStarted) {
        chatStarted = true;
      }
      const data = await api("/chat", { method: "POST", body: JSON.stringify({ message: msg }) });
      applyChat(data);
    } catch (e) {
      const soft = "うまく返事できなかったみたい。もう一度送ってくれる？";
      if (dialogueEl) dialogueEl.textContent = soft;
      setErr(e.message || String(e));
      try {
        if (luna) luna.reactToText(soft, { fallback: "sad" });
      } catch (_) {}
    } finally {
      busy = false;
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  async function startChat() {
    if (chatStarted) return;
    chatStarted = true;
    showLocalGreeting();
    try {
      const data = await api("/chat/start", { method: "POST", body: JSON.stringify({ message: "" }) });
      applyChat(data);
    } catch (e) {
      setErr(e.message);
      // Keep local greeting visible; allow retry on next luna tab focus.
      chatStarted = false;
      showLocalGreeting();
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
        if (name === "health" || name === "money") switchTab(name);
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
      voiceOn = !voiceOn;
      syncVoiceBtn();
      if (!voiceOn) stopLunaSpeech();
      else ttsFailStreak = 0;
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
    if (studyComplete) {
      studyComplete.onclick = async () => {
        if (!currentStudyLessonId) return;
        const id = currentStudyLessonId;
        closeStudyModal();
        await completeJourneyLesson(id);
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
