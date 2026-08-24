(function () {
  const CLASSES = [
    { id: "swordsman", label: "剣士", icon: "⚔️" },
    { id: "archer", label: "弓使い", icon: "🏹" },
    { id: "mage", label: "魔法使い", icon: "🪄" },
    { id: "priest", label: "牧師", icon: "✨" },
  ];
  const CLASS_DESC = {
    swordsman: "近接攻撃に優れたバランス型。初心者におすすめ！",
    archer: "遠距離から狙う俊敏なアタッカー",
    mage: "強力な魔法で学びを深めるスペシャリスト",
    priest: "仲間を支え回復するヒーラー",
  };
  const SKILLS = [
    { icon: "あ", label: "日本語", cls: "pink" },
    { icon: "EN", label: "英語", cls: "blue" },
    { icon: "数", label: "数学", cls: "yellow" },
    { icon: "理", label: "理科", cls: "green" },
    { icon: "💼", label: "生活", cls: "purple" },
    { icon: "🎯", label: "進路", cls: "orange" },
  ];
  const SKILL_CLS = {
    pink: "linear-gradient(135deg,#ff5d9d,#ff91c8)",
    blue: "linear-gradient(135deg,#497cff,#31d2ff)",
    yellow: "linear-gradient(135deg,#f6b61f,#ffdb68)",
    green: "linear-gradient(135deg,#1bb874,#6de8b8)",
    purple: "linear-gradient(135deg,#7a5cff,#b47aff)",
    orange: "linear-gradient(135deg,#ff7a38,#ffbf42)",
  };
  const DEFAULT_QUESTS = [
    { title: "25分学習する", quest_type: "daily_study", subject: "general", icon: "📘", color: SKILL_CLS.blue },
    { title: "今日の目標を1つ決める", quest_type: "homework", subject: "life", icon: "✅", color: SKILL_CLS.green },
    { title: "LUNAに近況を話す", quest_type: "daily_study", subject: "mental", icon: "💬", color: SKILL_CLS.pink },
  ];
  const QUICK = {
    health: ["睡眠7時間目標", "水を意識する", "少し疲れた", "調子いい"],
    money: ["時給を記録", "欲しいものメモ", "今月の支出", "貯金目標"],
    schedule: ["テスト日程", "バイトシフト", "締切あり", "空き時間"],
  };
  const ROUTE_COLORS = ["pink", "blue", "green"];
  const MAP_POSITIONS = [
    { left: "12%", top: "55%" },
    { left: "35%", top: "25%" },
    { left: "58%", top: "45%" },
    { left: "78%", top: "20%" },
    { left: "88%", top: "60%" },
  ];

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

  const errEl = document.getElementById("err");
  const lunaMainView = document.getElementById("lunaMainView");
  const settingsView = document.getElementById("settingsView");
  let scheduleSuggestions = [];

  function fmtDateJa(iso) {
    const d = new Date(iso + "T12:00:00");
    const wd = ["日", "月", "火", "水", "木", "金", "土"][d.getDay()];
    return d.getFullYear() + "年" + (d.getMonth() + 1) + "月" + d.getDate() + "日（" + wd + "）";
  }

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function openSubview(name) {
    document.getElementById("sub-" + name).classList.remove("hidden");
    if (name === "schedule") loadScheduleView();
    if (name === "health") loadHealthView();
    if (name === "money") loadMoneyView();
  }

  function closeSubview(name) {
    document.getElementById("sub-" + name).classList.add("hidden");
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
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    document.getElementById("tab-" + name).classList.add("active");
    const nav = document.querySelector('.nav-item[data-tab="' + name + '"]');
    if (nav) nav.classList.add("active");
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
    renderHomeHeader();
    renderClassPicker();
    renderSkills();
    renderMap();
    renderQuests();
    loadCareerTab();
  }

  function renderClassPicker() {
    const el = document.getElementById("classPicker");
    if (!el) return;
    el.innerHTML = "";
    CLASSES.forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "class-btn" + (c.id === selectedClass ? " active" : "");
      b.innerHTML = '<span class="class-icon">' + c.icon + '</span>' + c.label;
      b.onclick = () => selectClass(c.id);
      el.appendChild(b);
    });
  }

  async function selectClass(classId) {
    selectedClass = classId;
    localStorage.setItem("luna_class", classId);
    renderClassPicker();
    renderHomeHeader();
    const cluster = findClusterForClass(classId);
    if (cluster) {
      try {
        await api("/career/select", {
          method: "POST",
          body: JSON.stringify({ cluster_id: cluster.id, rpg_class: classId }),
        });
        await refreshCore();
      } catch (e) {
        setErr(e.message);
      }
    }
  }

  function findClusterForClass(classId) {
    return (window._careerClusters || []).find((c) => c.rpg_class === classId);
  }

  function classLabel(id) {
    if (!id) return "冒険者";
    return classLabels[id] || CLASSES.find((c) => c.id === id)?.label || id;
  }

  function renderHomeHeader() {
    const cls = rpgData.class_id || selectedClass;
    const user = stateData.user_display_name || "冒険者";
    const lv = stateData.level || 1;
    const exp = stateData.total_exp || 0;
    const prog = expProgress(exp, lv);
    const badge = document.getElementById("homeClassBadge");
    if (badge) badge.textContent = "現在のクラス：" + classLabel(cls);
    const role = document.getElementById("homeRoleName");
    if (role) role.textContent = user;
    const desc = document.getElementById("homeRoleDesc");
    if (desc) desc.textContent = CLASS_DESC[cls] || CLASS_DESC.swordsman;
    const expL = document.getElementById("homeExpLabel");
    if (expL) expL.textContent = "EXP " + prog.cur + " / " + prog.need;
    const lvL = document.getElementById("homeLvLabel");
    if (lvL) lvL.textContent = "Lv." + lv;
    const bar = document.getElementById("homeExpBar");
    if (bar) bar.style.width = prog.pct + "%";
    document.getElementById("myName").textContent = user;
  }

  async function loadHomeSummary() {
    try {
      const s = await api("/home/summary");
      document.getElementById("homeDate").textContent = s.date_ja || "";
      document.getElementById("stSchedule").textContent = s.schedule?.label || "予定なし";
      document.getElementById("stHealth").textContent = s.health?.label || "良好";
      document.getElementById("stGoals").textContent = s.goals?.label || "—";
    } catch (_) {}
  }

  function renderTodoList(elId, items, opts) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = "";
    if (!items.length) {
      el.innerHTML = '<p class="hint">まだありません</p>';
      return;
    }
    items.forEach((ev) => {
      const row = document.createElement("div");
      row.className = "todo-row" + (ev.done ? " done" : "") + (opts?.future ? " future" : "");
      const time = ev.time ? ev.time + " · " : "";
      row.innerHTML = '<span style="flex:1">' + time + ev.title + "</span>";
      if (!opts?.readonly) {
        const btn = document.createElement("button");
        btn.textContent = ev.done ? "戻す" : "完了";
        btn.onclick = () => toggleEventDone(ev.id, !ev.done);
        row.appendChild(btn);
      }
      el.appendChild(row);
    });
  }

  async function loadScheduleView() {
    try {
      const data = await api("/schedule/events");
      document.getElementById("schedDateCard").textContent = fmtDateJa(data.today);
      document.getElementById("addDate").value = data.today;
      renderTodoList("todayOpenList", data.today_open || []);
      renderTodoList("pastDoneList", data.past_done || [], { readonly: true });
      renderTodoList("futureList", data.future || [], { future: true });
      const sug = await api("/schedule/suggestions");
      scheduleSuggestions = sug.suggestions || [];
      const box = document.getElementById("suggestBox");
      const list = document.getElementById("suggestList");
      if (scheduleSuggestions.length) {
        box.style.display = "block";
        list.innerHTML = "";
        scheduleSuggestions.forEach((s, i) => {
          const row = document.createElement("div");
          row.className = "suggest-item";
          row.innerHTML =
            "<span>" +
            s.date +
            " " +
            (s.time || "") +
            " " +
            s.title +
            '<br><small style="color:var(--muted)">' +
            s.reason_ja +
            "</small></span>";
          list.appendChild(row);
        });
      } else {
        box.style.display = "none";
      }
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
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
    const title = document.getElementById("addTitle").value.trim();
    const date = document.getElementById("addDate").value;
    const time = document.getElementById("addTime").value;
    if (!title || !date) return;
    try {
      await api("/schedule/events", {
        method: "POST",
        body: JSON.stringify({ title, date, time: time || null }),
      });
      document.getElementById("addTitle").value = "";
      document.getElementById("addTime").value = "";
      document.getElementById("addForm").classList.remove("open");
      await loadScheduleView();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function applySuggestions() {
    try {
      await api("/schedule/suggestions/apply", {
        method: "POST",
        body: JSON.stringify({ apply_all: true }),
      });
      await loadScheduleView();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function loadHealthView() {
    try {
      const data = await api("/life/health");
      const st = data.structured || {};
      if (st.score) document.getElementById("healthSleep").textContent = st.score;
      if (st.steps) document.getElementById("healthSteps").textContent = st.steps;
    } catch (_) {}
  }

  async function loadMoneyView() {
    try {
      const data = await api("/life/money");
      const base = data.baseline || {};
      const inEl = document.getElementById("moneyIn");
      const outEl = document.getElementById("moneyOut");
      if (inEl) inEl.textContent = base.income || base.収入 || "—";
      if (outEl) outEl.textContent = base.expense || base.支出 || "—";
      const lines = [];
      Object.entries(base).forEach(([k, v]) => lines.push("・" + k + ": " + v));
      (data.notes || []).slice(-6).forEach((n) => lines.push("＋ " + n.text));
      document.getElementById("moneyNotes").textContent = lines.length ? lines.join("\n") : "追記はLUNAに話すか、メニューから追加できます。";
    } catch (_) {}
  }

  function renderSkills() {
    const grid = document.getElementById("skillGrid");
    if (!grid) return;
    const lv = stateData.level || 1;
    grid.innerHTML = "";
    SKILLS.forEach((s, i) => {
      const locked = i > lv + 1;
      const div = document.createElement("div");
      div.className = "skill";
      div.style.opacity = locked ? ".45" : "1";
      div.innerHTML =
        '<div class="icon" style="background:' +
        SKILL_CLS[s.cls] +
        '">' +
        s.icon +
        '</div><strong>' +
        s.label +
        '</strong><em style="font-style:normal;color:var(--muted);font-size:.58rem">Lv.' +
        Math.max(1, Math.min(lv, i + 1)) +
        "</em>";
      grid.appendChild(div);
    });
  }

  function renderMap() {
    const path = document.getElementById("mapPath");
    if (!path) return;
    path.innerHTML = "";
    const list = regions.length
      ? regions
      : [
          { label_ja: "始まりの平原", unlocked: true, current: true },
          { label_ja: "学習の森", unlocked: false },
          { label_ja: "試練の丘", unlocked: false },
          { label_ja: "中間の峡谷", unlocked: false },
          { label_ja: "期末の城", unlocked: false },
        ];
    list.forEach((r, i) => {
      const pos = MAP_POSITIONS[i] || MAP_POSITIONS[MAP_POSITIONS.length - 1];
      const node = document.createElement("div");
      node.className = "map-node" + (r.current ? " current" : "") + (!r.unlocked ? " locked" : "");
      node.style.left = pos.left;
      node.style.top = pos.top;
      node.innerHTML = '<div class="dot"></div>' + (r.label_ja || r.id);
      path.appendChild(node);
    });
    const cur = list.find((r) => r.current) || list[0];
    const lbl = document.getElementById("mapRegionLabel");
    if (lbl) lbl.textContent = "現在のエリア：" + (cur ? cur.label_ja : "始まりの平原");
  }

  function renderQuests() {
    const list = document.getElementById("questList");
    if (!list) return;
    list.innerHTML = "";
    const active = (rpgData.active_quests || []).slice(0, 5);
    const items = active.length
      ? active.map((q) => ({
          id: q.id,
          title: q.title,
          quest_type: q.quest_type || "daily_study",
          subject: q.subject,
          icon: "📘",
          color: SKILL_CLS.blue,
          active: true,
        }))
      : DEFAULT_QUESTS.map((q) => Object.assign({}, q, { active: false }));

    items.forEach((q) => {
      const row = document.createElement("div");
      row.className = "quest-item";
      row.innerHTML =
        '<div class="quest-icon" style="background:' +
        q.color +
        '">' +
        q.icon +
        '</div><div class="quest-text"><strong>' +
        q.title +
        '</strong><span>+' +
        (q.quest_type === "daily_study" ? "10" : "12") +
        ' EXP</span></div><div class="quest-actions"></div>';
      const actions = row.querySelector(".quest-actions");
      const btn = document.createElement("button");
      btn.className = q.active ? "done" : "go";
      btn.textContent = q.active ? "達成" : "開始";
      btn.onclick = () => (q.active ? completeQuest(q) : startQuest(q));
      actions.appendChild(btn);
      list.appendChild(row);
    });
  }

  async function startQuest(q) {
    try {
      await api("/rpg/quest/start", {
        method: "POST",
        body: JSON.stringify({ title: q.title, quest_type: q.quest_type, subject: q.subject }),
      });
      await refreshCore();
      renderQuests();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function completeQuest(q) {
    try {
      await api("/rpg/activity/complete", {
        method: "POST",
        body: JSON.stringify({
          title: q.title,
          quest_type: q.quest_type,
          subject: q.subject,
          quest_id: q.id,
        }),
      });
      if (luna) luna.applyEmotion("cheer", 1500);
      await refreshCore();
      renderQuests();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function loadCareerTab() {
    try {
      const [port, suggest] = await Promise.all([
        api("/rpg/portfolio"),
        api("/career/suggest", {
          method: "POST",
          body: JSON.stringify({ personality_text: "", hobbies_text: "", save: false, top_k: 3 }),
        }),
      ]);
      renderPortfolioStats(port);
      const story = document.getElementById("storyBox");
      if (story) story.textContent = port.story_ja || "冒険は始まったばかりです。";
      renderRoutes(suggest.suggestions || []);
    } catch (_) {
      const story = document.getElementById("storyBox");
      if (story) story.textContent = "LUNAと話してから、探索ルートを見てみましょう。";
    }
  }

  function renderPortfolioStats(port) {
    const row = document.getElementById("portfolioStats");
    if (!row) return;
    const s = port.summary || {};
    row.innerHTML =
      '<div class="stat-box" style="background:linear-gradient(135deg,#c9a227,#8b6914)"><span>クエスト</span><strong>' +
      (s.quests_completed || 0) +
      '</strong></div><div class="stat-box" style="background:linear-gradient(135deg,#497cff,#31d2ff)"><span>装備</span><strong>' +
      (s.tests_equipment || 0) +
      '</strong></div><div class="stat-box" style="background:linear-gradient(135deg,#7a5cff,#b47aff)"><span>ボス</span><strong>' +
      (s.bosses_cleared || 0) +
      "</strong></div>";
  }

  function renderRoutes(suggestions) {
    const el = document.getElementById("routeList");
    if (!el) return;
    el.innerHTML = "";
    if (!suggestions.length) {
      el.innerHTML = '<p class="hint">LUNAに話すと、進路の候補が出てきます。</p>';
      return;
    }
    suggestions.slice(0, 3).forEach((s, i) => {
      const card = document.createElement("div");
      card.className = "route-card " + ROUTE_COLORS[i % ROUTE_COLORS.length];
      card.innerHTML =
        "<h4>" +
        (s.label_ja || s.cluster_id) +
        "</h4><p>" +
        (s.reason_ja || "") +
        '</p><button type="button">このルートを選ぶ</button>';
      card.querySelector("button").onclick = () => selectRoute(s);
      el.appendChild(card);
    });
  }

  async function selectRoute(s) {
    try {
      await api("/career/select", {
        method: "POST",
        body: JSON.stringify({
          cluster_id: s.cluster_id,
          decided_career: (s.example_jobs && s.example_jobs[0]) || null,
          rpg_class: s.rpg_class,
        }),
      });
      if (s.rpg_class) {
        selectedClass = s.rpg_class;
        localStorage.setItem("luna_class", s.rpg_class);
      }
      await refreshCore();
      renderClassPicker();
      loadCareerTab();
    } catch (e) {
      setErr(e.message);
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

  function syncMiniLuna() {
    const mini = document.getElementById("homeMiniLuna");
    const sprite = document.getElementById("lunaSprite");
    if (mini && sprite && sprite.src) mini.src = sprite.src;
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
    syncMiniLuna();
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
      btn.onclick = () => switchTab(btn.dataset.tab);
    });
    document.querySelectorAll(".fsq-sub").forEach((btn) => {
      btn.onclick = () => switchFsqSub(btn.dataset.fsq);
    });
    document.querySelectorAll("[data-open]").forEach((el) => {
      el.onclick = () => openSubview(el.dataset.open);
    });
    document.querySelectorAll("[data-back]").forEach((el) => {
      el.onclick = () => closeSubview(el.dataset.back);
    });
    document.querySelectorAll("[data-ask]").forEach((el) => {
      el.onclick = async () => {
        closeSubview("health");
        closeSubview("money");
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
    document.getElementById("toggleAddBtn").onclick = () => document.getElementById("addForm").classList.add("open");
    document.getElementById("addCancelBtn").onclick = () => document.getElementById("addForm").classList.remove("open");
    document.getElementById("addSaveBtn").onclick = () => addScheduleEvent();
    document.getElementById("applySuggestBtn").onclick = () => applySuggestions();
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
    document.getElementById("refreshCareerBtn").onclick = () => loadCareerTab();
    document.getElementById("logoutBtn").onclick = () => {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    };
    const mini = document.getElementById("homeMiniLuna");
    if (mini) mini.onclick = () => luna && luna.onTap && luna.onTap();
  }

  async function refreshCore() {
    try {
      const [state, rpg, tax, brain] = await Promise.all([
        api("/state/me"),
        api("/rpg/me"),
        api("/career/taxonomy"),
        api("/brain/me"),
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
      if (rpgData.class_id) selectedClass = rpgData.class_id;
      const modePill = document.getElementById("modePill");
      if (modePill) modePill.textContent = brain.mode || "—";
      renderHomeHeader();
      renderSkills();
      renderMap();
      renderQuests();
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
    } catch (_) {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    }
  }

  boot();
})();
