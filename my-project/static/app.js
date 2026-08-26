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
        "曜日」に同じ予定を入れる\n" +
        "キャンセル = この日だけ"
    );
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
      renderHomeToday(s.schedule?.today_items || []);
    } catch (_) {}
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

  function eventsForDate(iso) {
    return allScheduleEvents
      .filter((e) => e.date === iso)
      .sort((a, b) => (a.time || "99:99").localeCompare(b.time || "99:99"));
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

  function selectCalendarDay(iso) {
    selectedDate = iso;
    const parts = iso.split("-").map(Number);
    calCursor = new Date(parts[0], parts[1] - 1, 1);
    const dateInput = document.getElementById("addDate");
    if (dateInput) dateInput.value = iso;
    renderCalendar();
    renderDayEvents();
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
      acts.appendChild(doneBtn);
      acts.appendChild(editBtn);
      row.appendChild(acts);
      attachSwipeDelete(row, () => deleteScheduleEvent(ev.id));
      el.appendChild(row);
    });
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

  async function loadScheduleView(opts) {
    const preserveCursor = !!(opts && opts.preserveCursor);
    const skipHome = !!(opts && opts.skipHome);
    try {
      const focus = selectedDate || document.getElementById("addDate")?.value || todayIso();
      const data = await api("/schedule/events?date=" + encodeURIComponent(focus));
      allScheduleEvents = data.events || [];
      datesWithEvents = new Set(data.dates_with_events || []);
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

  async function deleteScheduleEvent(id) {
    if (!id) return;
    const ev = (allScheduleEvents || []).find((e) => e.id === id);
    const isRecurring = !!(ev && (ev.recurrence_id || ev.recurrence || String(id).startsWith("rec-")));
    let scope = "this";
    if (isRecurring) {
      const delAll = confirm(
        "繰り返し予定です。\n\n同じ曜日のこれから先の予定もすべて削除しますか？\n\nOK = すべて削除\nキャンセル = この日だけ削除"
      );
      // If user cancels the confirm entirely we still need a second confirm for "this day"?
      // Browser confirm: OK=all, Cancel=this day only — but Cancel also means "don't delete all".
      // Use a clearer two-step:
      if (delAll) {
        if (!confirm("本当にすべての繰り返し予定を削除しますか？")) return;
        scope = "all";
      } else {
        if (!confirm("この日の予定だけ削除しますか？")) return;
        scope = "this";
      }
    } else {
      if (!confirm("この予定を削除しますか？")) return;
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

  async function loadHealthView() {
    try {
      const d = await api("/life/health/dashboard");
      document.getElementById("healthScoreBig").textContent = d.score;
      document.getElementById("healthStatus").textContent = d.status_ja || "良好";
      document.getElementById("healthSleep").textContent = (d.sleep_history || []).slice(-1)[0]?.score || d.score;
      document.getElementById("healthSteps").textContent = Number(d.steps || 0).toLocaleString("ja-JP");
      document.getElementById("healthHr").textContent = d.heart_rate;
      document.getElementById("healthWater").textContent = d.water_glasses + "/" + d.water_goal;
      document.getElementById("healthMessage").textContent = d.message_ja || "";
      const sleepScore = (d.sleep_history || []).slice(-1)[0]?.score || d.score;
      document.getElementById("editHealthScore").value = d.score;
      document.getElementById("editHealthSleep").value = sleepScore;
      document.getElementById("editHealthSteps").value = d.steps;
      document.getElementById("editHealthHr").value = d.heart_rate;
      document.getElementById("editHealthWater").value = d.water_glasses;

      const glassRow = document.getElementById("waterGlasses");
      if (glassRow) {
        glassRow.innerHTML = "";
        for (let i = 0; i < (d.water_goal || 8); i++) {
          const g = document.createElement("div");
          g.className = "water-glass" + (i < (d.water_glasses || 0) ? " fill" : "");
          glassRow.appendChild(g);
        }
      }

      const sleepLabels = (d.sleep_history || []).map((x) => x.month);
      const sleepData = (d.sleep_history || []).map((x) => x.score);
      makeChart("healthSleep", "healthSleepChart", {
        type: "line",
        data: {
          labels: sleepLabels,
          datasets: [
            {
              data: sleepData,
              borderColor: "#9b7ed9",
              backgroundColor: "rgba(155,126,217,.15)",
              fill: true,
              tension: 0.35,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { min: 50, max: 100, ticks: { stepSize: 10 } }, x: { grid: { display: false } } },
        },
      });

      const stepLabels = (d.steps_history || []).map((x) => x.month);
      const stepData = (d.steps_history || []).map((x) => x.steps);
      makeChart("healthSteps", "healthStepsChart", {
        type: "bar",
        data: {
          labels: stepLabels,
          datasets: [
            {
              data: stepData,
              backgroundColor: ["#b4aee8", "#9b7ed9", "#f0a8c8", "#6ec9b8", "#e8b86d", "#7b5eb8"],
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { display: false } }, y: { beginAtZero: true } },
        },
      });
    } catch (e) {
      setErr(e.message);
    }
  }

  async function loadMoneyView() {
    try {
      const d = await api("/life/money/dashboard");
      document.getElementById("moneyIn").textContent = fmtYen(d.income);
      document.getElementById("moneyOut").textContent = fmtYen(d.expense);
      document.getElementById("moneyInBar").style.width = (d.income_pct || 0) + "%";
      document.getElementById("moneyOutBar").style.width = (d.expense_pct || 0) + "%";
      document.getElementById("moneySavings").textContent = fmtYen(d.savings_total);
      document.getElementById("moneySavingsPct").textContent = (d.savings_pct || 0) + "%";
      document.getElementById("moneyMessage").textContent = d.message_ja || "";
      document.getElementById("editMoneyIn").value = d.income;
      document.getElementById("editMoneyOut").value = d.expense;
      document.getElementById("editMoneySavings").value = d.savings_total;
      document.getElementById("editMoneyBalance").value = d.current_balance;

      const balLabels = (d.balance_history || []).map((x) => x.month);
      const balData = (d.balance_history || []).map((x) => x.balance);
      makeChart("moneyBalance", "moneyBalanceChart", {
        type: "line",
        data: {
          labels: balLabels,
          datasets: [
            {
              data: balData,
              borderColor: "#497cff",
              backgroundColor: "rgba(73,124,255,.12)",
              fill: true,
              tension: 0.35,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { display: false } } },
        },
      });

      const cats = d.expense_categories || [];
      makeChart("moneyCategory", "moneyCategoryChart", {
        type: "bar",
        data: {
          labels: cats.map((c) => c.name),
          datasets: [
            {
              data: cats.map((c) => c.amount),
              backgroundColor: ["#9b7ed9", "#f0a8c8", "#6ec9b8", "#e8b86d", "#497cff"],
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { display: false } }, y: { beginAtZero: true } },
        },
      });

      const accEl = document.getElementById("moneyAccounts");
      if (accEl) {
        accEl.innerHTML = "";
        (d.accounts || []).forEach((a) => {
          const row = document.createElement("div");
          row.className = "account-row";
          row.innerHTML =
            "<span>" +
            a.name +
            '</span><div class="bar"><span style="width:' +
            (a.pct || 0) +
            '%"></span></div><strong>' +
            fmtYen(a.amount) +
            "</strong>";
          accEl.appendChild(row);
        });
      }

      const lines = [];
      Object.entries(d.baseline || {}).forEach(([k, v]) => lines.push("・" + k + ": " + v));
      (d.notes || []).forEach((n) => lines.push("＋ " + n.text));
      document.getElementById("moneyNotes").textContent = lines.length ? lines.join("\n") : "追記はLUNAに話すか、メニューから追加できます。";
    } catch (e) {
      setErr(e.message);
    }
  }

  async function saveHealthMetrics() {
    try {
      const sleep = Number(document.getElementById("editHealthSleep").value);
      const score = Number(document.getElementById("editHealthScore").value);
      const steps = Number(document.getElementById("editHealthSteps").value);
      const hr = Number(document.getElementById("editHealthHr").value);
      const water = Number(document.getElementById("editHealthWater").value);
      await api("/life/health/dashboard", {
        method: "PATCH",
        body: JSON.stringify({
          structured: {
            score,
            steps,
            heart_rate: hr,
            water_glasses: water,
            sleep_history: [
              { month: "1月", score: Math.max(50, sleep - 8) },
              { month: "2月", score: Math.max(50, sleep - 5) },
              { month: "3月", score: Math.max(50, sleep - 3) },
              { month: "4月", score: Math.max(50, sleep - 1) },
              { month: "5月", score: sleep },
              { month: "6月", score: sleep },
            ],
            steps_history: [
              { month: "1月", steps: Math.round(steps * 0.75) },
              { month: "2月", steps: Math.round(steps * 0.82) },
              { month: "3月", steps: Math.round(steps * 0.88) },
              { month: "4月", steps: Math.round(steps * 0.94) },
              { month: "5月", steps: Math.round(steps * 0.98) },
              { month: "6月", steps },
            ],
          },
          note: "健康数値を手動更新",
        }),
      });
      await loadHealthView();
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function saveMoneyMetrics() {
    try {
      const income = Number(document.getElementById("editMoneyIn").value);
      const expense = Number(document.getElementById("editMoneyOut").value);
      const savings = Number(document.getElementById("editMoneySavings").value);
      const balance = Number(document.getElementById("editMoneyBalance").value);
      await api("/life/money/dashboard", {
        method: "PATCH",
        body: JSON.stringify({
          structured: {
            income,
            expense,
            savings_total: savings,
            current_balance: balance,
            balance_history: [
              { month: "1月", balance: Math.round(balance * 0.85) },
              { month: "2月", balance: Math.round(balance * 0.9) },
              { month: "3月", balance: Math.round(balance * 0.94) },
              { month: "4月", balance: Math.round(balance * 0.97) },
              { month: "5月", balance },
            ],
          },
          note: "家計数値を手動更新",
        }),
      });
      await loadMoneyView();
      await loadHomeSummary();
    } catch (e) {
      setErr(e.message);
    }
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
        closeSubview(el.dataset.back);
        setNavActive("luna");
        switchTab("luna");
      };
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
    document.getElementById("toggleAddBtn").onclick = () => {
      resetAddForm(selectedDate || todayIso());
      document.getElementById("addForm").classList.add("open");
    };
    document.getElementById("addCancelBtn").onclick = () => resetAddForm(selectedDate || todayIso());
    document.getElementById("addSaveBtn").onclick = () => addScheduleEvent();
    document.getElementById("calPrev").onclick = () => shiftCalendarMonth(-1);
    document.getElementById("calNext").onclick = () => shiftCalendarMonth(1);
    const saveHealthBtn = document.getElementById("saveHealthBtn");
    if (saveHealthBtn) saveHealthBtn.onclick = () => saveHealthMetrics();
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
    document.getElementById("refreshCareerBtn").onclick = () => loadCareerTab();
    document.getElementById("logoutBtn").onclick = () => {
      LunaAuth.clearToken();
      LunaAuth.goLogin("/app");
    };
    const mini = document.getElementById("lunaStage");
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
