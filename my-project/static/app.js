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
  let currentTab = "home";
  let currentModule = "health";
  let stateData = { level: 1, total_exp: 0, companion_name: null, user_display_name: null };
  let rpgData = { class_id: null, region_id: "tutorial_plains", active_quests: [] };
  let regions = [];
  let careerData = { career_path: {}, rpg: {} };
  let portfolioData = null;
  let classLabels = {};
  let selectedClass = localStorage.getItem("luna_class") || "swordsman";

  const errEl = document.getElementById("err");

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
    const panel = document.getElementById("tab-" + name);
    const nav = document.querySelector('.nav-item[data-tab="' + name + '"]');
    if (panel) panel.classList.add("active");
    if (nav) nav.classList.add("active");
    if (name === "chat" && !chatStarted) startChat();
    if (name === "career") loadCareerTab();
    window.scrollTo(0, 0);
  }

  function renderClassPicker() {
    const el = document.getElementById("classPicker");
    el.innerHTML = "";
    CLASSES.forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "class-btn" + (c.id === selectedClass ? " active" : "");
      b.innerHTML = '<span class="class-icon">' + c.icon + '</span><span class="class-label">' + c.label + "</span>";
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
    const clusters = window._careerClusters || [];
    return clusters.find((c) => c.rpg_class === classId) || clusters[0];
  }

  function classLabel(id) {
    if (!id) return "冒険者";
    return classLabels[id] || CLASSES.find((c) => c.id === id)?.label || id;
  }

  function renderHomeHeader() {
    const cls = rpgData.class_id || selectedClass;
    const name = stateData.companion_name || "LUNA";
    const user = stateData.user_display_name || "冒険者";
    const lv = stateData.level || 1;
    const exp = stateData.total_exp || 0;
    const prog = expProgress(exp, lv);
    document.getElementById("homeUserPill").textContent = user;
    document.getElementById("homeClassBadge").textContent = "現在のクラス：" + classLabel(cls);
    document.getElementById("homeRoleName").textContent = name;
    document.getElementById("homeRoleDesc").textContent = CLASS_DESC[cls] || CLASS_DESC.swordsman;
    document.getElementById("homeExpLabel").textContent = "EXP " + prog.cur + " / " + prog.need;
    document.getElementById("homeLvLabel").textContent = "Lv." + lv;
    document.getElementById("homeExpBar").style.width = prog.pct + "%";
    document.getElementById("myName").textContent = user;
    document.getElementById("mySub").textContent = "Lv." + lv + " · EXP " + exp;
    const now = new Date();
    document.getElementById("clockLabel").textContent =
      now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0");
  }

  function renderSkills() {
    const grid = document.getElementById("skillGrid");
    const lv = stateData.level || 1;
    grid.innerHTML = "";
    SKILLS.forEach((s, i) => {
      const locked = i > lv + 1;
      const div = document.createElement("div");
      div.className = "skill" + (locked ? " locked" : "");
      div.style.opacity = locked ? ".45" : "1";
      div.innerHTML =
        '<div class="icon" style="background:' +
        SKILL_CLS[s.cls] +
        '">' +
        s.icon +
        '</div><strong>' +
        s.label +
        '</strong><em>Lv.' +
        Math.max(1, Math.min(lv, i + 1)) +
        "</em>";
      grid.appendChild(div);
    });
  }

  function renderMap() {
    const path = document.getElementById("mapPath");
    path.innerHTML = "";
    const list = regions.length ? regions : [
      { id: "tutorial_plains", label_ja: "始まりの平原", unlocked: true, current: true },
      { id: "study_forest", label_ja: "学習の森", unlocked: false },
      { id: "exam_hills", label_ja: "試練の丘", unlocked: false },
      { id: "midterm_canyon", label_ja: "中間の峡谷", unlocked: false },
      { id: "final_castle", label_ja: "期末の城", unlocked: false },
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
    document.getElementById("mapRegionLabel").textContent =
      "現在のエリア：" + (cur ? cur.label_ja : "始まりの平原");
  }

  function renderQuests() {
    const list = document.getElementById("questList");
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
        " EXP</span></div><div class="quest-actions"></div>";
      const actions = row.querySelector(".quest-actions");
      if (!q.active) {
        const start = document.createElement("button");
        start.className = "go";
        start.textContent = "開始";
        start.onclick = () => startQuest(q);
        actions.appendChild(start);
      } else {
        const done = document.createElement("button");
        done.className = "done";
        done.textContent = "達成";
        done.onclick = () => completeQuest(q);
        actions.appendChild(done);
      }
      list.appendChild(row);
    });
  }

  async function startQuest(q) {
    try {
      await api("/rpg/quest/start", {
        method: "POST",
        body: JSON.stringify({
          title: q.title,
          quest_type: q.quest_type,
          subject: q.subject,
        }),
      });
      await refreshCore();
      renderQuests();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function completeQuest(q) {
    try {
      const data = await api("/rpg/activity/complete", {
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
      if (data.exp_gain) setErr("");
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
      portfolioData = port;
      renderPortfolioStats(port);
      document.getElementById("storyBox").textContent = port.story_ja || "冒険は始まったばかりです。";
      renderRoutes(suggest.suggestions || []);
    } catch (e) {
      document.getElementById("storyBox").textContent = "プロフィールを充実させると、あらすじが育ちます。";
      setErr(e.message);
    }
  }

  function renderPortfolioStats(port) {
    const s = port.summary || {};
    const row = document.getElementById("portfolioStats");
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
    el.innerHTML = "";
    if (!suggestions.length) {
      el.innerHTML = '<p class="hint">チャットで自己紹介すると、探索ルートが提案されます。</p>';
      return;
    }
    suggestions.slice(0, 3).forEach((s, i) => {
      const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
      const card = document.createElement("div");
      card.className = "route-card " + color;
      card.innerHTML =
        "<h4>" +
        (s.cluster_label_ja || s.label_ja || s.cluster_id) +
        "</h4><p>" +
        (s.reason_ja || s.summary_ja || "あなたの特性に近いルートです。") +
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
      if (luna) luna.applyEmotion("wave", 1200);
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

  function syncVoiceBtn() {
    document.getElementById("voiceBtn").textContent = voiceOn ? "音声ON（タップでOFF）" : "音声OFF（タップでON）";
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

  function openLife(mod) {
    currentModule = mod;
    document.getElementById("lifeOverlay").classList.add("open");
    loadModule(mod);
  }

  function closeLife() {
    document.getElementById("lifeOverlay").classList.remove("open");
  }

  async function loadModule(mod) {
    document.getElementById("modMsg").textContent = "";
    document.getElementById("modNote").value = "";
    const q = document.getElementById("modQuick");
    q.innerHTML = "";
    (QUICK[mod] || []).forEach((label) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.onclick = () => {
        const ta = document.getElementById("modNote");
        ta.value = ta.value ? ta.value + " / " + label : label;
      };
      q.appendChild(b);
    });
    try {
      const data = await api("/life/" + mod);
      document.getElementById("modTitle").textContent = data.title_ja;
      document.getElementById("modHint").textContent = data.hint_ja;
      const lines = [];
      Object.entries(data.baseline || {}).forEach(([k, v]) => lines.push("・" + k + ": " + v));
      (data.notes || []).slice(-6).forEach((n) => lines.push("＋ " + n.text));
      document.getElementById("modBaseline").textContent = lines.length
        ? lines.join("\n")
        : "まだ情報がありません。";
    } catch (e) {
      setErr(e.message);
    }
  }

  async function refreshLifeSummary() {
    try {
      const life = await api("/life/modules");
      const map = { schedule: "lifeSchedule", health: "lifeHealth", money: "lifeMoney" };
      (life.modules || []).forEach((m) => {
        const el = document.getElementById(map[m.module]);
        if (!el) return;
        const n = (m.notes || []).length;
        const b = Object.keys(m.baseline || {}).length;
        el.textContent = n || b ? b + "+" + n : "開く";
      });
    } catch (_) {}
  }

  async function refreshCore() {
    try {
      const [state, rpg, career, tax] = await Promise.all([
        api("/state/me"),
        api("/rpg/me"),
        api("/career/me"),
        api("/career/taxonomy"),
      ]);
      stateData = {
        level: state.current_level || rpg.level || 1,
        total_exp: state.total_exp || rpg.total_exp || 0,
        companion_name: state.companion_name,
        user_display_name: state.user_display_name,
      };
      rpgData = rpg.rpg || {};
      regions = rpg.regions || [];
      careerData = career;
      window._careerClusters = tax.career_clusters || [];
      (tax.rpg_classes || []).forEach((c) => {
        classLabels[c.id] = c.label_ja;
      });
      if (rpgData.class_id) selectedClass = rpgData.class_id;
      renderHomeHeader();
      renderSkills();
      renderMap();
      renderQuests();
      refreshLifeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  function renderThemePicker() {
    const grid = document.getElementById("themeGrid");
    const cur = LunaTheme.currentTheme();
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
  }

  function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.onclick = () => switchTab(btn.dataset.tab);
    });
    document.getElementById("homeQuestCta").onclick = () => switchTab("quest");
    document.getElementById("questChatBtn").onclick = () => {
      switchTab("chat");
      sendMessage("今日のクエストについて相談したいです。");
    };
    document.getElementById("sendBtn").onclick = () => sendMessage(document.getElementById("message").value);
    document.getElementById("message").onkeydown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage(document.getElementById("message").value);
      }
    };
    document.getElementById("lifeHealthBtn").onclick = () => openLife("health");
    document.getElementById("lifeMoneyBtn").onclick = () => openLife("money");
    document.getElementById("lifeScheduleBtn").onclick = () => openLife("schedule");
    document.querySelectorAll(".life-card").forEach((c) => {
      c.onclick = () => openLife(c.dataset.life);
    });
    document.getElementById("modClose").onclick = closeLife;
    document.getElementById("modSave").onclick = async () => {
      const note = document.getElementById("modNote").value.trim();
      if (!note) return;
      try {
        await api("/life/" + currentModule, { method: "POST", body: JSON.stringify({ note }) });
        document.getElementById("modMsg").textContent = "追記しました";
        await loadModule(currentModule);
        await refreshLifeSummary();
      } catch (e) {
        setErr(e.message);
      }
    };
    document.getElementById("modAsk").onclick = async () => {
      const note = document.getElementById("modNote").value.trim();
      const labels = { health: "健康", money: "お金", schedule: "スケジュール" };
      closeLife();
      switchTab("chat");
      await sendMessage(
        note
          ? "【" + labels[currentModule] + "】追記：" + note + "。アドバイスをお願いします。"
          : "【" + labels[currentModule] + "】の状況を確認してください。"
      );
    };
    document.getElementById("morningBtn").onclick = async () => {
      try {
        const goal = prompt("今日の目標は？", "") || "";
        await api("/checkin/morning", { method: "POST", body: JSON.stringify({ goal }) });
        switchTab("chat");
        await sendMessage(goal ? "今日の目標は「" + goal + "」。朝チェックインお願いします。" : "朝チェックインお願いします。");
      } catch (e) {
        setErr(e.message);
      }
    };
    document.getElementById("eveningBtn").onclick = async () => {
      try {
        await api("/checkin/evening", { method: "POST", body: JSON.stringify({}) });
        switchTab("chat");
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
    document.getElementById("lifeOverlay").onclick = (e) => {
      if (e.target.id === "lifeOverlay") closeLife();
    };
  }

  async function boot() {
    if (!LunaAuth.requireLogin("/app")) return;
    token = LunaAuth.getToken();
    syncVoiceBtn();
    renderClassPicker();
    renderThemePicker();
    bindEvents();
    try {
      const me = await api("/auth/me");
      if (me.is_admin) document.getElementById("adminLink").classList.remove("hidden");
      luna = new LunaAvatar(document.getElementById("lunaSprite"), null, document.getElementById("lunaStage"));
      await refreshCore();
    } catch (_) {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    }
  }

  boot();
})();
