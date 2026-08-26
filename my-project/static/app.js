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

  let token = LunaAuth.getToken();
  let busy = false;
  let luna = null;
  let chatStarted = false;
  let firstChat = true;
  let voiceOn = localStorage.getItem("luna_voice") !== "0";
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
    errEl.textContent = msg || "";
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

  async function loadJourney() {
    const [st, mp] = await Promise.all([api("/journey/status"), api("/journey/map")]);
    journeyStatus = st || { selected: false };
    journeyMap = mp || { selected: false, stages: [], lessons: [], bosses: [] };
    if (st.class_id) selectedClass = st.class_id;
    applyJourneyUi();
  }

  function showFsqOnboarding(show) {
    const onboard = document.getElementById("fsq-onboard");
    const sub = document.getElementById("fsqSubnav");
    const sections = ["fsq-home", "fsq-map", "fsq-career"];
    if (onboard) onboard.style.display = show ? "block" : "none";
    if (sub) sub.style.display = show ? "none" : "flex";
    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (show) el.classList.remove("active");
      else if (id === "fsq-home") el.classList.add("active");
    });
    if (!show) switchFsqSub("home");
  }

  function applyJourneyUi() {
    const needOnboard = reselectJourney || !journeyStatus.selected;
    showFsqOnboarding(needOnboard);
    if (needOnboard) {
      renderClassPicker();
      document.getElementById("onboardClassStep").style.display = onboardStep === "class" ? "block" : "none";
      document.getElementById("onboardCareerStep").style.display = onboardStep === "career" ? "block" : "none";
      if (onboardStep === "career") renderCareerPicker();
      return;
    }
    renderHomeHeader();
    renderSkills();
    renderNextLesson();
    renderMap();
    renderLessons();
    renderBosses();
    renderCareerPortfolio();
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
      b.innerHTML = '<span class="class-icon">' + c.icon + "</span>" + c.label;
      b.onclick = () => {
        selectedClass = c.id;
        localStorage.setItem("luna_class", c.id);
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

  function applyAppearance(wrap, img, appearance) {
    if (!wrap || !img) return;
    const ap = appearance || {};
    wrap.className = "hero-avatar " + (ap.css_classes || "");
    if (ap.sprite) img.src = ap.sprite;
  }

  function renderHomeHeader() {
    const cls = journeyStatus.class_id || rpgData.class_id || selectedClass;
    const user = stateData.user_display_name || "冒険者";
    const lv = journeyStatus.level || stateData.level || 1;
    const exp = journeyStatus.total_exp || stateData.total_exp || 0;
    const prog = expProgress(exp, lv);
    const badge = document.getElementById("homeClassBadge");
    if (badge) {
      badge.textContent =
        "クラス：" +
        (journeyStatus.class_ja || classLabel(cls)) +
        " ／ 進化：" +
        (journeyStatus.rank_ja || "見習い");
    }
    const role = document.getElementById("homeRoleName");
    if (role) role.textContent = journeyStatus.career_title_ja || user;
    const desc = document.getElementById("homeRoleDesc");
    if (desc) {
      desc.textContent = journeyStatus.selected
        ? CLASS_DESC[cls] || "レッスンをクリアして装備とランクを上げよう。"
        : CLASS_DESC[cls] || CLASS_DESC.swordsman;
    }
    const expL = document.getElementById("homeExpLabel");
    if (expL) expL.textContent = "旅EXP " + (journeyStatus.journey_exp || 0) + " ／ 総EXP " + prog.cur;
    const lvL = document.getElementById("homeLvLabel");
    if (lvL) lvL.textContent = "Lv." + lv;
    const bar = document.getElementById("homeExpBar");
    if (bar) bar.style.width = prog.pct + "%";
    applyAppearance(
      document.getElementById("homeAvatarWrap"),
      document.getElementById("homeAvatarImg"),
      journeyStatus.appearance
    );
    const my = document.getElementById("myName");
    if (my) my.textContent = user;
  }

  function renderNextLesson() {
    const box = document.getElementById("nextLessonBox");
    if (!box) return;
    const les = journeyStatus.next_lesson;
    if (!les) {
      box.innerHTML = '<p class="hint" style="margin:0">次のレッスンはありません。マップのボスに挑戦しよう。</p>';
      return;
    }
    box.innerHTML =
      "<div><strong>" +
      (les.title_ja || les.id) +
      '</strong><div class="hint">+' +
      (les.exp || 0) +
      " EXP</div></div>";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "クリア";
    btn.onclick = () => completeJourneyLesson(les.id);
    box.appendChild(btn);
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
      showRewardModal("レッスン完了！", ["EXP +" + (res.exp_gained || 0), (res.lesson && res.lesson.title_ja) || ""], chips);
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
    const lbl = document.getElementById("mapRegionLabel");
    if (lbl) {
      lbl.textContent =
        "現在：" +
        (cur ? cur.label_ja : "始まりの平原") +
        (journeyStatus.career_title_ja ? "（" + journeyStatus.career_title_ja + "）" : "");
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
        btn.textContent = "クリア";
        btn.onclick = () => completeJourneyLesson(les.id);
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

  function speakJa(text) {
    if (!voiceOn || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ja-JP";
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

  async function applyChat(data) {
    document.getElementById("dialogue").textContent = data.dialogue || "";
    renderChips(data.suggested_replies || []);
    const emo = data.game_state && data.game_state.emotion;
    if (luna) {
      if (emo) luna.applyEmotion(emo);
      else luna.reactToText(data.dialogue || "", { greeting: firstChat, fallback: "happy" });
    }
    firstChat = false;
    speakJa(data.dialogue || "");
    await refreshCore();
  }

  async function sendMessage(text) {
    const msg = (text || "").trim();
    if (!msg || busy) return;
    busy = true;
    document.getElementById("sendBtn").disabled = true;
    setErr("");
    document.getElementById("message").value = "";
    if (luna) luna.reactToText(msg, { fallback: "think" });
    try {
      const data = await api("/chat", { method: "POST", body: JSON.stringify({ message: msg }) });
      await applyChat(data);
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      busy = false;
      document.getElementById("sendBtn").disabled = false;
    }
  }

  async function startChat() {
    if (chatStarted) return;
    chatStarted = true;
    try {
      const data = await api("/chat/start", { method: "POST", body: JSON.stringify({ message: "" }) });
      await applyChat(data);
    } catch (e) {
      setErr(e.message);
      chatStarted = false;
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
      if (!voiceOn) {
        window.speechSynthesis.cancel();
        if (luna) luna.stopLipSync();
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
      await refreshCore();
      await startChat();
      await loadHomeSummary();
      await checkMentalCheckin();
    } catch (_) {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    }
  }

  boot();
})();
