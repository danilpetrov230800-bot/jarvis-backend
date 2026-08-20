const logEl = document.getElementById("log");
const inputEl = document.getElementById("input");
const formEl = document.getElementById("composer");
const micBtn = document.getElementById("micBtn");
const hud = document.getElementById("hud");
const hudState = document.getElementById("hudState");
const heard = document.getElementById("heard");
const statusLine = document.getElementById("statusLine");
const settingsDlg = document.getElementById("settings");
const settingsForm = document.getElementById("settingsForm");

const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let listening = false;
let speaking = false;
let busy = false;
let settings = {};
let audioQueue = Promise.resolve();
let currentAudio = null;
let wakeArmedUntil = 0;
let ignoreVoiceUntil = 0;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function startStars() {
  const canvas = document.getElementById("stars");
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const stars = [];
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener("resize", resize);
  for (let i = 0; i < 140; i += 1) {
    stars.push({
      x: Math.random(),
      y: Math.random(),
      z: Math.random() * 1.4 + 0.2,
      p: Math.random() * Math.PI * 2,
    });
  }
  const tick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const star of stars) {
      star.p += 0.015 * star.z;
      const alpha = 0.15 + Math.abs(Math.sin(star.p)) * 0.75;
      ctx.fillStyle = `rgba(243, 237, 255, ${alpha})`;
      ctx.beginPath();
      ctx.arc(star.x * canvas.width, star.y * canvas.height, star.z, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(tick);
  };
  tick();
}

function setState(state, detail = "") {
  hud.className = `hud ${state}`;
  hudState.textContent = {
    idle: "NOVA",
    listening: "LISTEN",
    thinking: "THINK",
    speaking: "SPEAK",
  }[state] || "NOVA";
  statusLine.textContent = detail || {
    idle: "ожидание",
    listening: "слушаю вас",
    thinking: "думаю",
    speaking: "говорю",
  }[state] || detail;
}

function addMessage(role, text, sources = []) {
  const wrap = document.createElement("article");
  wrap.className = `msg ${role}`;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? (settings.user_name || "Вы") : (settings.assistant_name || "NOVA");
  wrap.appendChild(who);
  wrap.appendChild(document.createTextNode(text));
  if (sources.length) {
    const src = document.createElement("div");
    src.className = "sources";
    src.innerHTML = sources
      .slice(0, 5)
      .map((s) => `<a href="${escapeHtml(s.url)}" target="_blank" rel="noreferrer">${escapeHtml(s.title || s.url)}</a>`)
      .join(" · ");
    wrap.appendChild(src);
  }
  if (role === "assistant") {
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy-btn";
    copy.textContent = "копировать";
    copy.addEventListener("click", () => navigator.clipboard.writeText(text).catch(() => {}));
    wrap.appendChild(copy);
  }
  logEl.appendChild(wrap);
  logEl.scrollTop = logEl.scrollHeight;
}

async function speak(text) {
  if (!text) return;
  speaking = true;
  setState("speaking");
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("tts");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    await new Promise((resolve) => {
      const audio = new Audio(url);
      currentAudio = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        resolve();
      };
      audio.onerror = resolve;
      audio.play().catch(resolve);
    });
  } catch {
    await new Promise((resolve) => {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = "ru-RU";
      utter.onend = resolve;
      utter.onerror = resolve;
      speechSynthesis.speak(utter);
    });
  } finally {
    speaking = false;
    ignoreVoiceUntil = Date.now() + 1500;
    currentAudio = null;
    setState(listening ? "listening" : "idle");
  }
}

function stopSpeak() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (window.speechSynthesis) speechSynthesis.cancel();
  speaking = false;
  audioQueue = Promise.resolve();
  setState(listening ? "listening" : "idle");
}

async function sendText(text, voiceReply = true) {
  const value = (text || "").trim();
  if (!value || busy) return;
  busy = true;
  addMessage("user", value);
  inputEl.value = "";
  setState("thinking");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Ошибка ответа");
    addMessage("assistant", data.reply, data.sources || []);
    if (voiceReply) {
      audioQueue = audioQueue.then(() => speak(data.speech || data.reply));
    } else {
      setState("idle");
    }
  } catch (err) {
    addMessage("assistant", String(err.message || err));
    setState("idle");
  } finally {
    busy = false;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  sendText(inputEl.value, true);
});

function maybeWake(transcript) {
  if (Date.now() < ignoreVoiceUntil) return null;
  const t = transcript.trim();
  const lower = t.toLowerCase();
  const woke = /^(нова|nova|джарвис|jarvis)[,.\s:-]*/i.exec(lower);
  if (woke) {
    const command = t.slice(woke[0].length).trim();
    if (!command) {
      wakeArmedUntil = Date.now() + 8000;
      setState("listening", "жду команду");
      return null;
    }
    wakeArmedUntil = 0;
    return command;
  }
  if (Date.now() < wakeArmedUntil) {
    wakeArmedUntil = 0;
    return t;
  }
  return null;
}

function setupMic() {
  if (!SpeechRec) {
    micBtn.title = "Голосовой ввод поддерживается в Chrome или Edge";
    return;
  }
  recognition = new SpeechRec();
  recognition.lang = "ru-RU";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.onresult = (event) => {
    let finalText = "";
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const piece = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += piece;
      else interim += piece;
    }
    heard.textContent = interim || finalText;
    if (finalText && !speaking && !busy) {
      const command = maybeWake(finalText);
      if (command) sendText(command, true);
    }
  };
  recognition.onerror = () => setState("idle");
  recognition.onend = () => {
    if (listening) recognition.start();
  };
}

micBtn.addEventListener("click", () => {
  if (!recognition) {
    addMessage("assistant", "Голосовой ввод доступен в Chrome и Edge.");
    return;
  }
  listening = !listening;
  micBtn.classList.toggle("active", listening);
  if (listening) {
    recognition.start();
    setState("listening");
  } else {
    recognition.stop();
    setState("idle");
  }
});

document.getElementById("settingsBtn").addEventListener("click", async () => {
  await loadSettingsIntoForm();
  settingsDlg.showModal();
});
document.getElementById("closeSettings").addEventListener("click", () => settingsDlg.close());
document.getElementById("deleteKey").addEventListener("click", async () => {
  if (!confirm("Удалить сохранённый API-ключ?")) return;
  await api("/api/settings", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key: "" }),
  });
  settings.api_key_preview = "";
});
document.getElementById("resetBtn").addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  logEl.innerHTML = "";
  addMessage("assistant", "Память диалога очищена. Слушаю вас.");
});

document.getElementById("saveSettings").addEventListener("click", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(settingsForm).entries());
  if (!data.api_key) delete data.api_key;
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  settings = await (await fetch("/api/settings")).json();
  document.getElementById("assistantName").textContent = settings.assistant_name || "NOVA";
  settingsDlg.close();
});

async function loadSettingsIntoForm() {
  settings = await (await fetch("/api/settings")).json();
  const form = settingsForm;
  form.provider.value = settings.provider || "auto";
  form.model.value = settings.model || "";
  form.base_url.value = settings.base_url || "";
  form.user_name.value = settings.user_name || "";
  try {
    const voices = await (await fetch("/api/voices")).json();
    const select = form.tts_voice;
    select.innerHTML = "";
    for (const voice of voices.voices || []) {
      const opt = document.createElement("option");
      opt.value = voice.id;
      opt.textContent = `${voice.name} (${voice.gender})`;
      if (voice.id === settings.tts_voice) opt.selected = true;
      select.appendChild(opt);
    }
    if (!select.options.length) {
      select.innerHTML = '<option value="ru-RU-DmitryNeural">Dmitry</option>';
    }
  } catch {
    form.tts_voice.innerHTML = '<option value="ru-RU-DmitryNeural">Dmitry</option>';
  }
}

function inferProvider(key) {
  if (key.startsWith("gsk_")) return "groq";
  if (key.startsWith("sk-or-")) return "openrouter";
  if (key.startsWith("sk-")) return "openai";
  return "auto";
}

async function boot() {
  startStars();
  setupMic();
  try {
    settings = await (await fetch("/api/settings")).json();
    document.getElementById("assistantName").textContent = settings.assistant_name || "NOVA";
    addMessage(
      "assistant",
      "Я Nova. Работаю как приложение на этом компьютере. Скажите: «открой YouTube», «громче», «пробки Москва», «погода», «курс доллара», «мой ip». Кнопка «Виджет» сворачивает окно, «Стоп» прерывает голос.",
    );
    setState("idle", "онлайн");
  } catch {
    addMessage("assistant", "Не удалось связаться с ядром NOVA.");
  }
}

boot();

let widgetMode = false;

async function setWidget(on) {
  widgetMode = Boolean(on);
  document.body.classList.toggle("widget-mode", widgetMode);
  const btn = document.getElementById("widgetBtn");
  if (btn) btn.textContent = widgetMode ? "Развернуть" : "Виджет";
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_widget) {
      await window.pywebview.api.set_widget(widgetMode);
    }
  } catch {
    /* browser fallback keeps CSS-only widget */
  }
}

document.getElementById("widgetBtn").addEventListener("click", () => setWidget(!widgetMode));
hud.addEventListener("click", () => {
  if (widgetMode) setWidget(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && widgetMode) setWidget(false);
});

async function sendPc(action, value) {
  try {
    const res = await fetch("/api/pc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(value == null ? { action } : { action, value }),
    });
    const data = await res.json();
    if (!res.ok) {
      addMessage("assistant", data.detail || "Управление ПК доступно в Windows.");
      return;
    }
    statusLine.textContent = data.reply || action;
  } catch (err) {
    addMessage("assistant", String(err.message || err));
  }
}

document.getElementById("pcDock").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-pc]");
  if (!btn) return;
  sendPc(btn.getAttribute("data-pc"));
});

let brightTimer = null;
document.getElementById("brightRange").addEventListener("input", (event) => {
  const value = Number(event.target.value);
  clearTimeout(brightTimer);
  brightTimer = setTimeout(() => sendPc("brightness", value), 180);
});

document.getElementById("stopBtn").addEventListener("click", () => stopSpeak());
document.getElementById("chips").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-chat]");
  if (!btn) return;
  sendText(btn.getAttribute("data-chat"), true);
});

const workspace = document.getElementById("workspacePanel");
const workspaceTitle = document.getElementById("workspaceTitle");
const workspaceHelp = document.getElementById("workspaceHelp");
const workspaceForm = document.getElementById("workspaceForm");
const workspaceContent = document.getElementById("workspaceContent");
document.getElementById("workspaceClose").addEventListener("click", () => workspace.close());

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Операция не выполнена");
  return data;
}

function field(label, name, placeholder = "", wide = false) {
  return `<label class="${wide ? "wide" : ""}">${label}<input name="${name}" placeholder="${placeholder}" required /></label>`;
}

function cards(items, titleKey = "name") {
  workspaceContent.innerHTML = items.length ? items.map((item) => `
    <article class="data-card">
      <header><strong>${escapeHtml(item[titleKey] || item.title || item.content || item.action || "")}</strong>
      ${item.id ? `<button type="button" data-delete="${item.id}">Удалить</button>` : ""}</header>
      <small>${escapeHtml(item.kind || item.role || item.task_type || item.category || item.created_at || "")}</small>
      ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}
    </article>`).join("") : '<p class="hint">Записей пока нет.</p>';
}

async function openCollection(name) {
  const configs = {
    memory: {
      title: "Memory", help: "Сохраняются только записи, которые вы добавили явно.",
      form: `${field("Что запомнить", "content", "Предпочтение или факт", true)}
        <label>Тип<select name="kind"><option value="long_term">Long-term</option><option value="preference">Preference</option><option value="episodic">Episodic</option><option value="semantic">Semantic</option></select></label>
        ${field("Категория", "category", "general")}<button class="wide" type="submit">Запомнить</button>`,
      endpoint: "/api/memory", titleKey: "content",
    },
    skills: {
      title: "Skills", help: "Skill — именованная последовательность действий с явным триггером.",
      form: `${field("Название", "name")}${field("Trigger", "trigger", "режим работы")}
        ${field("Описание", "description", "", true)}${field("Действие", "action", "открой Chrome", true)}
        <button class="wide" type="submit">Сохранить Skill</button>`,
      endpoint: "/api/skills",
    },
    agents: {
      title: "Agents", help: "Специализированные агенты работают с ограниченными инструментами и разрешениями.",
      form: `${field("Имя", "name")}${field("Роль", "role", "Research Agent")}
        ${field("Инструкции", "instructions", "", true)}${field("Инструменты", "tools", "web_search, memory", true)}
        <button class="wide" type="submit">Создать Agent</button>`,
      endpoint: "/api/agents",
    },
    tasks: {
      title: "Tasks", help: "Локальный реестр одноразовых, повторяющихся и агентских задач.",
      form: `${field("Задача", "title", "", true)}
        <label>Тип<select name="task_type"><option>one-time</option><option>recurring</option><option>background</option><option>agent</option><option>reminder</option></select></label>
        ${field("Расписание", "schedule", "необязательно")}<button class="wide" type="submit">Добавить задачу</button>`,
      endpoint: "/api/tasks",
    },
  };
  const cfg = configs[name];
  workspaceTitle.textContent = cfg.title;
  workspaceHelp.textContent = cfg.help;
  workspaceForm.innerHTML = cfg.form;
  const reload = async () => cards(await api(cfg.endpoint), cfg.titleKey);
  workspaceForm.onsubmit = async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(workspaceForm).entries());
    if (name === "skills") payload.actions = [{ type: "command", value: payload.action }], delete payload.action;
    if (name === "agents") payload.tools = payload.tools.split(",").map((x) => x.trim()).filter(Boolean);
    await api(cfg.endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    workspaceForm.reset();
    await reload();
  };
  workspaceContent.onclick = async (event) => {
    const button = event.target.closest("[data-delete]");
    if (!button) return;
    await api(`${cfg.endpoint}/${button.dataset.delete}`, { method: "DELETE" });
    await reload();
  };
  await reload();
}

async function openPermissions() {
  workspaceTitle.textContent = "Permissions";
  workspaceHelp.textContent = "Опасные возможности отключены по умолчанию. Включайте только необходимые.";
  workspaceForm.innerHTML = "";
  const items = await api("/api/permissions");
  workspaceContent.innerHTML = items.map((item) => `
    <label class="data-card"><input type="checkbox" data-permission="${item.name}" ${item.enabled ? "checked" : ""} />
      <strong>${escapeHtml(item.name)}</strong> ${item.dangerous ? "— опасное разрешение" : ""}</label>`).join("");
  workspaceContent.onchange = async (event) => {
    const input = event.target.closest("[data-permission]");
    if (!input) return;
    if (input.checked && !confirm(`Включить ${input.dataset.permission}?`)) { input.checked = false; return; }
    await api(`/api/permissions/${input.dataset.permission}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: input.checked }),
    });
  };
}

async function openDiagnostics() {
  workspaceTitle.textContent = "NOVA Diagnostics";
  workspaceHelp.textContent = "Проверка ядра, хранилища, голоса, сети и разрешений.";
  workspaceForm.innerHTML = '<button type="submit">Проверить NOVA</button><button type="button" id="backupNow">Создать backup</button>';
  const run = async () => {
    const data = await api("/api/diagnostics");
    workspaceContent.innerHTML = data.checks.map((item) => `<article class="data-card"><strong class="status-${item.status}">${item.status}</strong> ${escapeHtml(item.name)}<br><small>${escapeHtml(item.detail)}</small></article>`).join("");
  };
  workspaceForm.onsubmit = (event) => { event.preventDefault(); run(); };
  workspaceForm.querySelector("#backupNow").onclick = async () => {
    const data = await api("/api/backup", { method: "POST" });
    workspaceHelp.textContent = `Backup: ${data.path}`;
  };
  await run();
}

async function openTools() {
  workspaceTitle.textContent = "Local Tools";
  workspaceHelp.textContent = "Поиск файлов выполняется только в профиле пользователя и требует READ_FILES.";
  workspaceForm.innerHTML = `${field("Папка", "path", "C:\\Users\\...")}${field("Маска", "pattern", "*.pdf")}<button class="wide">Найти файлы</button>`;
  workspaceForm.onsubmit = async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(workspaceForm).entries());
    const found = await api("/api/tools/files", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operation: "find", ...data }) });
    cards(found, "path");
  };
  workspaceContent.innerHTML = "";
}

async function openResearch() {
  workspaceTitle.textContent = "Creator Research / OSINT";
  workspaceHelp.textContent = "Только открытые источники. NOVA не обходит авторизацию, CAPTCHA, paywall или ограничения доступа.";
  workspaceForm.innerHTML = `${field("Публичный поисковый запрос", "query", "", true)}<button class="wide">Искать в открытых источниках</button>`;
  workspaceForm.onsubmit = (event) => {
    event.preventDefault();
    const query = new FormData(workspaceForm).get("query");
    workspace.close();
    sendText(`погугли ${query}`, false);
  };
  workspaceContent.innerHTML = "";
}

async function openLogs() {
  workspaceTitle.textContent = "Audit Logs";
  workspaceHelp.textContent = "Ключи и пароли в журнал не записываются.";
  workspaceForm.innerHTML = "";
  cards(await api("/api/logs"), "action");
}

document.querySelector(".sidebar").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-section]");
  if (!button) return;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  const section = button.dataset.section;
  if (section === "home" || section === "chat") { workspace.close(); inputEl.focus(); return; }
  workspace.showModal();
  try {
    if (["memory", "skills", "agents", "tasks"].includes(section)) await openCollection(section);
    else if (section === "permissions") await openPermissions();
    else if (section === "diagnostics") await openDiagnostics();
    else if (section === "tools") await openTools();
    else if (section === "research") await openResearch();
    else if (section === "logs") await openLogs();
  } catch (err) {
    workspaceContent.innerHTML = `<p class="error">${escapeHtml(err.message || err)}</p>`;
  }
});
