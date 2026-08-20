const api = (path, opts = {}) =>
  fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  }).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "Не удалось выполнить действие.");
    return data;
  });

const state = {
  view: "home",
  status: {},
  settings: {},
  conversation: [],
  agentMode: false,
  listening: false,
  wakeArmed: true,
  recognition: null,
  ttsPlaying: false,
};

const views = document.getElementById("views");
const modal = document.getElementById("modal");
const tts = document.getElementById("tts");

function $(sel) { return document.querySelector(sel); }
function h(html) { const d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstElementChild; }

function showModal(html) {
  modal.classList.remove("hidden");
  modal.innerHTML = `<div class="card">${html}</div>`;
  modal.onclick = (e) => { if (e.target === modal) hideModal(); };
}
function hideModal() { modal.classList.add("hidden"); modal.innerHTML = ""; }

async function refreshStatus() {
  state.status = await api("/api/status");
  state.settings = await api("/api/settings");
  document.body.dataset.theme = state.settings.theme || "dark";
  document.documentElement.style.zoom = ({ "100": "1", "125": "1.25", "150": "1.5", "200": "2" }[state.settings.ui_scale] || "1");
  $("#statusLine").textContent = state.status.offline ? "Offline mode" : "Онлайн";
  $("#offlineBadge").classList.toggle("hidden", !state.status.offline);
  $("#taskLine").textContent = state.status.first_run ? "Первый запуск" : "Готова к работе";
  if (state.status.first_run) openWizard();
}

function navTo(view) {
  state.view = view;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const titles = {
    home: "NOVA", chat: "Чат", agents: "Агенты", skills: "Навыки", memory: "Память",
    tools: "Инструменты", tasks: "Задачи", research: "Исследование", settings: "Настройки", logs: "Журнал",
  };
  $("#viewTitle").textContent = titles[view] || "NOVA";
  render();
}

document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) navTo(btn.dataset.view);
});

async function render() {
  const fn = {
    home: renderHome, chat: renderChat, agents: renderAgents, skills: renderSkills,
    memory: renderMemory, tools: renderTools, tasks: renderTasks, research: renderResearch,
    settings: renderSettings, logs: renderLogs,
  }[state.view];
  await fn();
}

function renderHome() {
  views.innerHTML = `
    <div class="grid cols-2">
      <div class="card chat">
        <div class="messages" id="homeMsgs"></div>
        <div class="composer">
          <textarea id="homeInput" placeholder="Спросите NOVA или скажите «Нова»…"></textarea>
          <button class="primary" id="homeSend">Отправить</button>
        </div>
      </div>
      <div class="grid">
        <div class="card">
          <h3>Сейчас</h3>
          <p class="muted" id="nowTask">Нет активной задачи</p>
          <div class="steps" id="homeSteps"></div>
        </div>
        <div class="card">
          <h3>Быстрые действия</h3>
          <div class="actions">
            <button class="ghost" data-q="который час">Время</button>
            <button class="ghost" data-q="что происходит с компьютером">Система</button>
            <button class="ghost" data-q="помощь">Возможности</button>
            <button class="ghost" data-q="сделай скриншот">Скриншот</button>
          </div>
        </div>
      </div>
    </div>`;
  bindChat("homeInput", "homeSend", "homeMsgs");
  views.querySelectorAll("[data-q]").forEach((b) => b.onclick = () => sendChat(b.dataset.q));
}

async function renderChat() {
  const data = await api("/api/conversation");
  state.conversation = data.messages || [];
  views.innerHTML = `
    <div class="card chat">
      <div class="messages" id="chatMsgs"></div>
      <div class="composer">
        <textarea id="chatInput" placeholder="Сообщение для NOVA"></textarea>
        <button class="primary" id="chatSend">Отправить</button>
      </div>
    </div>`;
  paintMessages("chatMsgs", state.conversation.map((m) => ({ role: m.role === "user" ? "user" : "nova", text: m.content })));
  bindChat("chatInput", "chatSend", "chatMsgs");
}

async function renderAgents() {
  const data = await api("/api/agents");
  views.innerHTML = `
    <div class="card">
      <div class="actions" style="margin-bottom:12px">
        <input id="agentGoal" placeholder="Задача для агента" />
        <button class="primary" id="runAgent">Запустить</button>
        <button class="ghost" id="newAgent">Создать агента</button>
      </div>
      <div id="agentSteps" class="steps"></div>
      ${(data.agents || []).map((a) => `
        <div class="list-row">
          <div><b>${esc(a.name)}</b><div class="muted">${esc(a.role)} — ${esc(a.instructions)}</div></div>
          <div class="actions">
            <button class="ghost" data-toggle="${a.id}">${a.enabled ? "Выключить" : "Включить"}</button>
          </div>
        </div>`).join("") || `<div class="empty">Агентов нет</div>`}
    </div>`;
  $("#runAgent").onclick = async () => {
    const goal = $("#agentGoal").value.trim();
    if (!goal) return;
    $("#nowTask") && ($("#nowTask").textContent = "Планирую задачу");
    const run = await api("/api/agents/run", { method: "POST", body: { text: goal } });
    $("#agentSteps").innerHTML = (run.steps || []).map((s) => `<div class="step"><b>${esc(s.title)}</b><div class="muted">${esc(s.status)}</div><div>${esc(s.detail || "")}</div></div>`).join("");
  };
  $("#newAgent").onclick = () => showModal(`
    <h3>Новый агент</h3>
    <div class="wizard">
      <input id="naName" placeholder="Имя" />
      <select id="naRole">${["research","coding","file","system","creative","testing","automation","general"].map((r)=>`<option>${r}</option>`).join("")}</select>
      <textarea id="naInst" placeholder="Инструкции"></textarea>
      <div class="actions"><button class="primary" id="naSave">Сохранить</button><button class="ghost" id="naClose">Закрыть</button></div>
    </div>`);
  modal.addEventListener("click", async (e) => {
    if (e.target.id === "naClose") hideModal();
    if (e.target.id === "naSave") {
      await api("/api/agents", { method: "POST", body: { name: $("#naName").value, role: $("#naRole").value, instructions: $("#naInst").value } });
      hideModal(); render();
    }
  }, { once: true });
  views.querySelectorAll("[data-toggle]").forEach((b) => b.onclick = async () => {
    const id = b.dataset.toggle;
    const agent = data.agents.find((x) => String(x.id) === String(id));
    await api(`/api/agents/${id}`, { method: "POST", body: { enabled: !agent.enabled } });
    render();
  });
}

async function renderSkills() {
  const data = await api("/api/skills");
  views.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <h3>Конструктор навыка</h3>
        <input id="skName" placeholder="Имя" />
        <input id="skTrigger" placeholder="Триггер, например: я ухожу" style="margin-top:8px" />
        <p class="muted">Перетащите действия в последовательность</p>
        <div id="palette">
          ${[["open_app","Открыть приложение"],["close_app","Закрыть приложение"],["volume_mute","Выключить музыку"],["lock_pc","Заблокировать ПК"],["delay","Пауза 2 сек"]].map(([t,l]) => `<div class="skill-action" draggable="true" data-type="${t}">${l}</div>`).join("")}
        </div>
        <div class="drop" id="seq"></div>
        <div class="actions" style="margin-top:10px">
          <button class="primary" id="saveSkill">Сохранить навык</button>
          <button class="ghost" id="testSkillDraft">Тест</button>
        </div>
      </div>
      <div class="card">
        <h3>Сохранённые</h3>
        ${(data.skills || []).map((s) => `
          <div class="list-row">
            <div><b>${esc(s.name)}</b><div class="muted">${esc(s.trigger)}</div></div>
            <div class="actions">
              <button class="ghost" data-test="${s.id}">Тест</button>
              <button class="danger" data-del="${s.id}">Удалить</button>
            </div>
          </div>`).join("") || `<div class="empty">Навыков пока нет</div>`}
      </div>
    </div>`;
  const seq = $("#seq");
  views.querySelectorAll(".skill-action").forEach((el) => {
    el.addEventListener("dragstart", (e) => e.dataTransfer.setData("type", el.dataset.type));
  });
  seq.addEventListener("dragover", (e) => e.preventDefault());
  seq.addEventListener("drop", (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("type");
    const node = h(`<div class="skill-action" data-type="${type}">${type}</div>`);
    seq.appendChild(node);
  });
  $("#saveSkill").onclick = async () => {
    const actions = [...seq.querySelectorAll("[data-type]")].map((n) => {
      if (n.dataset.type === "delay") return { type: "delay", seconds: 2 };
      return { type: "tool", name: n.dataset.type, args: n.dataset.type === "open_app" ? { name: "explorer" } : {} };
    });
    await api("/api/skills", { method: "POST", body: { name: $("#skName").value || $("#skTrigger").value, trigger: $("#skTrigger").value, actions } });
    render();
  };
  views.querySelectorAll("[data-test]").forEach((b) => b.onclick = async () => {
    const res = await api(`/api/skills/${b.dataset.test}/test`, { method: "POST" });
    addMessage("nova", res.reply || "Готово.");
    navTo("chat");
  });
  views.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
    await api(`/api/skills/${b.dataset.del}`, { method: "DELETE" });
    render();
  });
}

async function renderMemory() {
  const data = await api("/api/memory");
  views.innerHTML = `
    <div class="card">
      <div class="actions" style="margin-bottom:12px">
        <input id="memQ" placeholder="Поиск" />
        <input id="memText" placeholder="Новый факт" />
        <select id="memKind">${["long_term","preference","episodic","semantic","skill"].map((k)=>`<option>${k}</option>`).join("")}</select>
        <button class="primary" id="memAdd">Сохранить</button>
        <button class="ghost" id="memExport">Экспорт</button>
        <button class="danger" id="memClear">Очистить</button>
      </div>
      ${(data.items || []).map((m) => `
        <div class="list-row">
          <div><b>${esc(m.title || m.kind)}</b><div>${esc(m.content)}</div><div class="muted">${esc(m.kind)} · важность ${m.importance}</div></div>
          <button class="danger" data-del="${m.id}">Удалить</button>
        </div>`).join("") || `<div class="empty">Память пуста</div>`}
    </div>`;
  $("#memAdd").onclick = async () => {
    await api("/api/memory", { method: "POST", body: { content: $("#memText").value, kind: $("#memKind").value } });
    render();
  };
  $("#memQ").onkeydown = async (e) => {
    if (e.key === "Enter") {
      const found = await api("/api/memory?q=" + encodeURIComponent($("#memQ").value));
      views.querySelector(".card").insertAdjacentHTML("beforeend", `<pre>${esc(JSON.stringify(found.items, null, 2))}</pre>`);
    }
  };
  $("#memExport").onclick = async () => {
    const exp = await api("/api/memory/export");
    const blob = new Blob([JSON.stringify(exp, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "nova-memory.json"; a.click();
  };
  $("#memClear").onclick = async () => { await api("/api/memory/clear", { method: "POST" }); render(); };
  views.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => { await api(`/api/memory/${b.dataset.del}`, { method: "DELETE" }); render(); });
}

async function renderTools() {
  const data = await api("/api/tools");
  views.innerHTML = `<div class="grid cols-3">${(data.tools || []).map((t) => `
    <div class="card">
      <b>${esc(t.title)}</b>
      <p class="muted">${esc(t.description)}</p>
      <p class="muted">${esc(t.permission)}${t.dangerous ? " · опасный" : ""}</p>
      <button class="ghost" data-run="${t.name}">Запустить</button>
    </div>`).join("")}</div>`;
  views.querySelectorAll("[data-run]").forEach((b) => b.onclick = () => runToolInteractive(b.dataset.run));
}

async function runToolInteractive(name) {
  const argMap = {
    calculator: { expr: prompt("Выражение", "24*7") },
    find_files: { query: prompt("Что найти", "pdf"), extension: "pdf" },
    create_file: { path: prompt("Путь файла", "nova-note.txt"), content: "NOVA" },
    open_app: { name: prompt("Приложение", "notepad") },
    get_weather: { location: prompt("Город", "Москва") },
    web_search: { query: prompt("Запрос", "NOVA") },
  };
  const res = await api("/api/tools/run", { method: "POST", body: { name, args: argMap[name] || {} } });
  await maybeConfirm(res);
  showModal(`<h3>${esc(name)}</h3><pre style="white-space:pre-wrap">${esc(res.reply || JSON.stringify(res))}</pre><button class="ghost" onclick="document.getElementById('modal').classList.add('hidden')">OK</button>`);
}

async function maybeConfirm(res) {
  if (!res.needs_confirmation) return res;
  const ok = confirm(res.confirmation_summary || "Подтвердить опасное действие?");
  if (!ok) return res;
  return api("/api/confirm", { method: "POST", body: { token: res.confirmation_token } });
}

async function renderTasks() {
  const data = await api("/api/tasks");
  views.innerHTML = `
    <div class="card">
      <div class="actions">
        <input id="taskTitle" placeholder="Название задачи" />
        <select id="taskKind"><option>one-time</option><option>recurring</option><option>background</option><option>agent</option><option>reminder</option></select>
        <button class="primary" id="taskAdd">Создать</button>
      </div>
      ${(data.tasks || []).map((t) => `
        <div class="list-row">
          <div><b>${esc(t.title)}</b><div class="muted">${esc(t.kind)} · ${esc(t.status)}</div></div>
          <div class="actions">
            <button class="ghost" data-pause="${t.id}">Пауза</button>
            <button class="danger" data-cancel="${t.id}">Отмена</button>
          </div>
        </div>`).join("") || `<div class="empty">Задач нет</div>`}
    </div>`;
  $("#taskAdd").onclick = async () => {
    await api("/api/tasks", { method: "POST", body: { title: $("#taskTitle").value, kind: $("#taskKind").value } });
    render();
  };
  views.querySelectorAll("[data-pause]").forEach((b) => b.onclick = async () => { await api(`/api/tasks/${b.dataset.pause}/pause`, { method: "POST" }); render(); });
  views.querySelectorAll("[data-cancel]").forEach((b) => b.onclick = async () => { await api(`/api/tasks/${b.dataset.cancel}/cancel`, { method: "POST" }); render(); });
}

async function renderResearch() {
  const settings = state.settings;
  views.innerHTML = `
    <div class="card">
      <p>Закрытый режим открытых источников. Без обхода паролей, CAPTCHA и закрытых страниц.</p>
      ${settings.research_enabled ? `
        <input id="rid" placeholder="Открытый идентификатор" />
        <div class="actions" style="margin-top:8px">
          <button class="primary" id="rgo">Искать публичные профили</button>
        </div>
        <pre id="rout" style="white-space:pre-wrap"></pre>` : `<p class="warn">Включите режим в Настройки → Research и разрешение RESEARCH.</p>`}
    </div>`;
  const go = $("#rgo");
  if (go) go.onclick = async () => {
    try {
      const res = await api("/api/research", { method: "POST", body: { identifier: $("#rid").value } });
      $("#rout").textContent = res.reply || JSON.stringify(res, null, 2);
    } catch (err) {
      $("#rout").textContent = err.message;
    }
  };
}

async function renderSettings() {
  const s = await api("/api/settings");
  const perms = await api("/api/permissions");
  const voices = await api("/api/voices").catch(() => ({ voices: [] }));
  const sections = [
    ["General", `
      <label>Имя<input name="user_name" value="${esc(s.user_name || "")}"></label>
      <label>Имя NOVA<input name="assistant_name" value="${esc(s.assistant_name || "NOVA")}"></label>`],
    ["AI", `
      <label>Провайдер
        <select name="ai_provider">${["local","openai","ollama","compatible"].map((p)=>`<option ${s.ai_provider===p?"selected":""}>${p}</option>`).join("")}</select>
      </label>
      <label>Модель<input name="ai_model" value="${esc(s.ai_model || "")}"></label>
      <label>Base URL<input name="ai_base_url" value="${esc(s.ai_base_url || "")}"></label>
      <label>API-ключ<input name="api_key" type="password" placeholder="${esc(s.api_key_preview || "не задан")}"></label>
      <div class="actions"><button class="danger" id="delKey">Удалить ключ</button></div>`],
    ["Voice", `
      <label>Голос<select name="tts_voice">${(voices.voices||[]).map((v)=>`<option value="${esc(v.id)}" ${s.tts_voice===v.id?"selected":""}>${esc(v.name)}</option>`).join("")}</select></label>
      <label>Скорость<input name="tts_rate" value="${esc(s.tts_rate)}"></label>
      <label>Громкость<input name="tts_volume" type="number" step="0.1" min="0" max="1" value="${s.tts_volume}"></label>
      <div class="actions"><button class="ghost" id="testMic">Тест микрофона</button><button class="ghost" id="testVoice">Тест голоса</button></div>`],
    ["Wake Word", `
      <label>Включён<select name="wake_word_enabled"><option value="true" ${s.wake_word_enabled?"selected":""}>да</option><option value="false" ${!s.wake_word_enabled?"selected":""}>нет</option></select></label>
      <label>Чувствительность<input name="wake_sensitivity" type="number" step="0.05" min="0.2" max="1" value="${s.wake_sensitivity}"></label>`],
    ["Memory", `<label>Подтверждать личное<select name="memory_confirm_personal"><option value="true" ${s.memory_confirm_personal?"selected":""}>да</option><option value="false">нет</option></select></label>`],
    ["Appearance", `
      <label>Тема<select name="theme"><option ${s.theme==="dark"?"selected":""}>dark</option><option ${s.theme==="light"?"selected":""}>light</option></select></label>
      <label>Масштаб<select name="ui_scale">${["100","125","150","200"].map((n)=>`<option ${s.ui_scale===n?"selected":""}>${n}</option>`).join("")}</select></label>`],
    ["Research", `<label>Режим исследования<select name="research_enabled"><option value="false">выкл</option><option value="true" ${s.research_enabled?"selected":""}>вкл</option></select></label>`],
    ["Permissions", (perms.permissions||[]).map((p)=>`
      <label>${p.key}${p.dangerous?" ⚠":""}
        <select data-perm="${p.key}"><option value="true" ${p.allowed?"selected":""}>вкл</option><option value="false" ${!p.allowed?"selected":""}>выкл</option></select>
      </label>`).join("")],
    ["Privacy", `<p class="muted">Секреты хранятся в защищённом хранилище. Логи не содержат ключей.</p>`],
    ["Notifications", `<label>Уведомления<select name="notifications_enabled"><option value="true" ${s.notifications_enabled?"selected":""}>вкл</option><option value="false">выкл</option></select></label>`],
    ["Storage", `<div class="actions"><button class="primary" id="doBackup">Резервная копия</button><button class="ghost" id="doBackupSecrets">Копия с секретами</button></div><div id="backupList"></div>`],
    ["Logs", `<button class="ghost" id="exportLogs">Экспорт логов</button>`],
    ["Updates", `<pre id="upd"></pre>`],
    ["Advanced", `<label>Офлайн<select name="offline_mode"><option value="false">нет</option><option value="true" ${s.offline_mode?"selected":""}>да</option></select></label>`],
  ];
  views.innerHTML = `<form id="setForm" class="grid">${sections.map(([t,b]) => `<div class="card"><h3>${t}</h3>${b}</div>`).join("")}
    <div class="actions"><button class="primary" type="submit">Сохранить</button></div></form>`;
  $("#setForm").onsubmit = async (e) => {
    e.preventDefault();
    const patch = {};
    new FormData(e.target).forEach((v, k) => {
      if (v === "true" || v === "false") patch[k] = v === "true";
      else patch[k] = v;
    });
    await api("/api/settings", { method: "POST", body: patch });
    for (const sel of views.querySelectorAll("[data-perm]")) {
      await api("/api/permissions", { method: "POST", body: { key: sel.dataset.perm, allowed: sel.value === "true" } });
    }
    await refreshStatus();
    render();
  };
  $("#delKey") && ($("#delKey").onclick = async (e) => { e.preventDefault(); await api("/api/settings/delete-key", { method: "POST" }); render(); });
  $("#testVoice") && ($("#testVoice").onclick = async (e) => { e.preventDefault(); await speak("Привет, я NOVA."); });
  $("#testMic") && ($("#testMic").onclick = async (e) => { e.preventDefault(); startMic(true); });
  $("#doBackup") && ($("#doBackup").onclick = async (e) => { e.preventDefault(); const r = await api("/api/backup", { method: "POST", body: {} }); alert("Сохранено: " + r.path); });
  $("#doBackupSecrets") && ($("#doBackupSecrets").onclick = async (e) => { e.preventDefault(); if (!confirm("Включить секреты в копию?")) return; const r = await api("/api/backup", { method: "POST", body: { include_secrets: true } }); alert("Сохранено: " + r.path); });
  $("#exportLogs") && ($("#exportLogs").onclick = async (e) => { e.preventDefault(); const r = await api("/api/logs/export", { method: "POST" }); alert("Логи: " + r.path); });
  api("/api/updates").then((u) => { const el = $("#upd"); if (el) el.textContent = JSON.stringify(u, null, 2); });
  api("/api/backup").then((b) => {
    const el = $("#backupList");
    if (el) el.innerHTML = (b.items || []).map((i) => `<div class="list-row"><span>${esc(i.name)}</span><button class="ghost" data-restore="${esc(i.path)}">Восстановить</button></div>`).join("");
    views.querySelectorAll("[data-restore]").forEach((btn) => btn.onclick = async (e) => {
      e.preventDefault();
      await api("/api/restore", { method: "POST", body: { path: btn.dataset.restore } });
      alert("Профиль восстановлен.");
    });
  });
}

async function renderLogs() {
  const data = await api("/api/logs");
  views.innerHTML = `<div class="card"><div class="actions"><button class="ghost" id="exp">Экспорт логов</button></div><pre style="white-space:pre-wrap; max-height:70vh; overflow:auto">${esc((data.lines || []).join("\n"))}</pre></div>`;
  $("#exp").onclick = async () => { const r = await api("/api/logs/export", { method: "POST" }); alert(r.path); };
}

function bindChat(inputId, sendId, boxId) {
  const send = async () => {
    const input = document.getElementById(inputId);
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    await sendChat(text, boxId);
  };
  document.getElementById(sendId).onclick = send;
  document.getElementById(inputId).addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
}

function paintMessages(id, items) {
  const box = document.getElementById(id);
  if (!box) return;
  box.innerHTML = items.map((m) => `<div class="bubble ${m.role}">${esc(m.text)}</div>`).join("");
  box.scrollTop = box.scrollHeight;
}

function addMessage(role, text, boxId) {
  const id = boxId || (state.view === "home" ? "homeMsgs" : "chatMsgs");
  const box = document.getElementById(id);
  if (!box) return;
  box.appendChild(h(`<div class="bubble ${role}">${esc(text)}</div>`));
  box.scrollTop = box.scrollHeight;
}

async function sendChat(text, boxId) {
  addMessage("user", text, boxId);
  $("#taskLine").textContent = state.agentMode ? "Планирую задачу" : "Думаю…";
  try {
    const path = state.agentMode ? "/api/agents/run" : "/api/chat";
    const res = await api(path, { method: "POST", body: { text, source: "text" } });
    if (res.needs_confirmation) {
      const confirmed = await maybeConfirm(res);
      addMessage("nova", confirmed.reply || res.reply || "Нужно подтверждение.", boxId);
      return;
    }
    const reply = res.reply || res.result || "Готово.";
    addMessage("nova", reply, boxId);
    if (res.agent && res.agent.steps) {
      const host = $("#homeSteps");
      if (host) host.innerHTML = res.agent.steps.map((s) => `<div class="step">${esc(s.title)} — ${esc(s.status)}</div>`).join("");
    }
    if (res.steps) {
      const host = $("#homeSteps") || $("#agentSteps");
      if (host) host.innerHTML = res.steps.map((s) => `<div class="step">${esc(s.title)} — ${esc(s.status)}</div>`).join("");
    }
    if (state.settings.tts_enabled !== false && reply) await speak(res.speech || reply);
  } catch (err) {
    addMessage("nova", "Произошла ошибка. Подробности в журнале.", boxId);
  }
  $("#taskLine").textContent = "Готова к работе";
}

async function speak(text) {
  try {
    state.ttsPlaying = true;
    if (state.recognition && state.listening) {
      try { state.recognition.stop(); } catch (_) {}
    }
    const res = await fetch("/api/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (!res.ok) { state.ttsPlaying = false; return; }
    const blob = await res.blob();
    tts.src = URL.createObjectURL(blob);
    tts.volume = Number(state.settings.tts_volume || 1);
    await tts.play();
    tts.onended = () => {
      state.ttsPlaying = false;
      if (state.wakeArmed) armWakeWord();
    };
  } catch (_) {
    state.ttsPlaying = false;
  }
}

function startMic(testOnly = false) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    alert("Распознавание речи недоступно. Можно писать текстом.");
    return;
  }
  const rec = new SR();
  rec.lang = state.settings.stt_lang || "ru-RU";
  rec.continuous = true;
  rec.interimResults = false;
  rec.onresult = async (ev) => {
    const text = ev.results[ev.results.length - 1][0].transcript.trim();
    if (!text || state.ttsPlaying) return;
    if (testOnly) { alert("Микрофон слышит: " + text); rec.stop(); return; }
    const wake = await api("/api/wake", { method: "POST", body: { text } }).catch(() => ({ wake: false }));
    if (wake.wake || !state.settings.wake_word_enabled) {
      $("#orb").classList.add("listening");
      const command = text.replace(/нова|nova/ig, "").trim();
      if (command) await sendChat(command);
      else addMessage("nova", "Слушаю.");
      setTimeout(() => $("#orb").classList.remove("listening"), 1200);
    }
  };
  rec.onerror = () => { state.listening = false; };
  rec.onend = () => { state.listening = false; if (state.wakeArmed && !state.ttsPlaying) setTimeout(armWakeWord, 400); };
  try { rec.start(); state.listening = true; state.recognition = rec; } catch (_) {}
}

function armWakeWord() {
  if (!state.settings.wake_word_enabled && !state.wakeArmed) return;
  if (!state.listening) startMic(false);
}

function openWizard() {
  showModal(`
    <div class="wizard">
      <h3>Добро пожаловать в NOVA</h3>
      <p class="muted">Можно ничего не настраивать — локальный режим уже работает.</p>
      <label>Провайдер
        <select id="wProv"><option value="local">Локальный</option><option value="openai">OpenAI</option><option value="ollama">Ollama</option></select>
      </label>
      <label>API-ключ (необязательно)<input id="wKey" type="password" /></label>
      <div class="actions">
        <button class="ghost" id="wMic">Тест микрофона</button>
        <button class="ghost" id="wVoice">Тест голоса</button>
      </div>
      <div class="actions">
        <button class="primary" id="wDone">Готово</button>
      </div>
    </div>`);
  $("#wMic").onclick = () => startMic(true);
  $("#wVoice").onclick = () => speak("Привет, я NOVA.");
  $("#wDone").onclick = async () => {
    await api("/api/settings", { method: "POST", body: { ai_provider: $("#wProv").value, api_key: $("#wKey").value } });
    await api("/api/first-run/complete", { method: "POST" });
    hideModal();
    await refreshStatus();
  };
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

$("#micBtn").onclick = () => startMic(false);
$("#wakeBtn").onclick = () => { state.wakeArmed = !state.wakeArmed; $("#wakeBtn").textContent = state.wakeArmed ? "Нова" : "Wake выкл"; if (state.wakeArmed) armWakeWord(); };
$("#agentModeBtn").onclick = () => { state.agentMode = !state.agentMode; $("#agentModeBtn").classList.toggle("primary", state.agentMode); };
$("#diagBtn").onclick = async () => {
  const res = await api("/api/diagnostics", { method: "POST" });
  showModal(`<h3>Диагностика: ${esc(res.status)}</h3>${(res.checks||[]).map((c)=>`<div class="list-row"><span>${esc(c.name)}</span><b class="${c.status==="PASS"?"pass":c.status==="WARNING"?"warn":"fail"}">${c.status}</b></div><div class="muted">${esc(c.detail)}</div>`).join("")}<button class="ghost" id="closeDiag">Закрыть</button>`);
  $("#closeDiag").onclick = hideModal;
};

refreshStatus().then(() => { navTo("home"); armWakeWord(); });
