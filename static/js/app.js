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
let lastSpoken = "";
let echoUntil = 0;

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

function addMessage(role, text, sources = [], steps = []) {
  const wrap = document.createElement("article");
  wrap.className = `msg ${role}`;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? (settings.user_name || "Вы") : (settings.assistant_name || "NOVA");
  wrap.appendChild(who);
  wrap.appendChild(document.createTextNode(text));
  if (steps && steps.length) {
    const st = document.createElement("div");
    st.className = "steps";
    st.textContent = steps.join(" → ");
    wrap.appendChild(st);
  }
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
  lastSpoken = String(text).toLowerCase();
  echoUntil = Date.now() + 900 + Math.min(4000, lastSpoken.length * 18);
  if (recognition && listening) {
    try { recognition.stop(); } catch { /* keep listening after */ }
  }
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
    addMessage("assistant", data.reply, data.sources || [], data.steps || []);
    if (voiceReply && settings.tts_enabled !== false) {
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

function looksLikeEcho(transcript) {
  const t = String(transcript || "").toLowerCase().trim();
  if (!t || !lastSpoken) return false;
  if (Date.now() < echoUntil) return true;
  return lastSpoken.includes(t) || t.includes(lastSpoken.slice(0, 28));
}

function maybeWake(transcript) {
  const t = transcript.trim();
  if (settings.wake_word === false) return t;
  const lower = t.toLowerCase();
  const woke = /^(нова|nova|джарвис|jarvis)[,.\s:-]*/i.exec(lower);
  if (woke) return t.slice(woke[0].length).trim() || t;
  return "";
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
    if (finalText && !speaking && !busy && !looksLikeEcho(finalText)) {
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
document.getElementById("resetBtn").addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  logEl.innerHTML = "";
  addMessage("assistant", "Память диалога очищена. Слушаю вас.");
});

document.getElementById("saveSettings").addEventListener("click", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(settingsForm).entries());
  if (!data.api_key) delete data.api_key;
  data.wake_word = Boolean(settingsForm.wake_word && settingsForm.wake_word.checked);
  data.tts_enabled = Boolean(settingsForm.tts_enabled && settingsForm.tts_enabled.checked);
  data.theme = settingsForm.theme ? settingsForm.theme.value : "dark";
  if (settingsForm.tts_rate) data.tts_rate = settingsForm.tts_rate.value;
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  settings = await (await fetch("/api/settings")).json();
  document.getElementById("assistantName").textContent = settings.assistant_name || "NOVA";
  applyTheme(settings.theme);
  settingsDlg.close();
});

async function loadSettingsIntoForm() {
  settings = await (await fetch("/api/settings")).json();
  const form = settingsForm;
  form.provider.value = settings.provider || "auto";
  form.model.value = settings.model || "";
  form.base_url.value = settings.base_url || "";
  form.user_name.value = settings.user_name || "";
  if (form.theme) form.theme.value = settings.theme || "dark";
  if (form.wake_word) form.wake_word.checked = settings.wake_word !== false;
    if (form.tts_enabled) form.tts_enabled.checked = settings.tts_enabled !== false;
    if (form.tts_rate) form.tts_rate.value = settings.tts_rate || "+12%";
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
    applyTheme(settings.theme);
    if (!settings.setup_done) showWizard(true);
    addMessage(
      "assistant",
      "Я Nova. Работаю как приложение на этом компьютере. Скажите: «открой YouTube», «громче», «пробки Москва», «погода», «курс доллара», «мой ip». Кнопка «Виджет» сворачивает окно, «Стоп» прерывает голос.",
    );
    await refreshStatus();
    setInterval(refreshStatus, 30000);
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

function applyTheme(theme) {
  document.body.classList.toggle("light", theme === "light");
}

function showWizard(on) {
  const el = document.getElementById("wizard");
  el.hidden = !on;
  el.classList.toggle("hidden", !on);
}

async function markSetupDone(extra = {}) {
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setup_done: true, ...extra }),
  });
  settings = await (await fetch("/api/settings")).json();
  showWizard(false);
}

document.getElementById("wizSkip").addEventListener("click", () => markSetupDone());
document.getElementById("wizSave").addEventListener("click", async () => {
  const extra = { user_name: document.getElementById("wizName").value, setup_done: true };
  const key = document.getElementById("wizKey").value.trim();
  if (key) extra.api_key = key;
  await markSetupDone(extra);
});

function showPage(name) {
  document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.getAttribute("data-page") === name));
  document.querySelectorAll("#sideNav button").forEach((el) => el.classList.toggle("active", el.getAttribute("data-page") === name));
  if (name === "memory") refreshMemory();
  if (name === "skills") refreshSkills();
  if (name === "tasks") refreshTasks();
  if (name === "tools") refreshPerms();
  if (name === "logs") refreshLogs();
  if (name === "agents") refreshAgents();
}

document.getElementById("sideNav").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-page]");
  if (!btn) return;
  const name = btn.getAttribute("data-page");
  if (name === "settings") {
    loadSettingsIntoForm().then(() => settingsDlg.showModal());
    return;
  }
  showPage(name);
});

async function refreshMemory() {
  const data = await (await fetch("/api/memory-long")).json();
  const box = document.getElementById("memoryList");
  box.innerHTML = "";
  for (const item of data.items || []) {
    const row = document.createElement("article");
    row.textContent = item.content;
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Удалить";
    del.addEventListener("click", async () => {
      await fetch(`/api/memory-long/${item.id}`, { method: "DELETE" });
      refreshMemory();
    });
    row.appendChild(del);
    box.appendChild(row);
  }
}

document.getElementById("memoryForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = document.getElementById("memoryText").value.trim();
  if (!content) return;
  await fetch("/api/memory-long", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  document.getElementById("memoryText").value = "";
  refreshMemory();
});

async function refreshSkills() {
  const data = await (await fetch("/api/skills")).json();
  const box = document.getElementById("skillList");
  box.innerHTML = "";
  for (const item of data.items || []) {
    const row = document.createElement("article");
    row.textContent = `${item.enabled ? "ON" : "OFF"} · ${item.trigger_text}`;
    const run = document.createElement("button");
    run.type = "button";
    run.textContent = "Тест";
    run.addEventListener("click", async () => {
      const res = await (await fetch(`/api/skills/${item.id}/run`, { method: "POST" })).json();
      addMessage("assistant", res.reply || "готово");
      showPage("home");
    });
    const tog = document.createElement("button");
    tog.type = "button";
    tog.textContent = "Вкл/выкл";
    tog.addEventListener("click", async () => {
      await fetch(`/api/skills/${item.id}/toggle`, { method: "POST" });
      refreshSkills();
    });
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Удалить";
    del.addEventListener("click", async () => {
      await fetch(`/api/skills/${item.id}`, { method: "DELETE" });
      refreshSkills();
    });
    row.appendChild(run);
    row.appendChild(tog);
    row.appendChild(del);
    box.appendChild(row);
  }
}

document.getElementById("skillForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const trigger = document.getElementById("skillTrigger").value.trim();
  const action_text = document.getElementById("skillAction").value.trim();
  if (!trigger || !action_text) return;
  await fetch("/api/skills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trigger, action_text, name: trigger }),
  });
  document.getElementById("skillTrigger").value = "";
  document.getElementById("skillAction").value = "";
  refreshSkills();
});

async function refreshTasks() {
  const data = await (await fetch("/api/tasks")).json();
  const box = document.getElementById("taskList");
  box.innerHTML = "";
  for (const item of data.items || []) {
    const row = document.createElement("article");
    row.textContent = `${item.status}: ${item.title}`;
    if (item.status === "active") {
      const stop = document.createElement("button");
      stop.type = "button";
      stop.textContent = "Отменить";
      stop.addEventListener("click", async () => {
        await fetch(`/api/tasks/${item.id}/cancel`, { method: "POST" });
        refreshTasks();
      });
      row.appendChild(stop);
    }
    box.appendChild(row);
  }
}

document.getElementById("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.getElementById("taskTitle").value.trim();
  const seconds = Number(document.getElementById("taskSeconds").value || 0);
  if (!title) return;
  await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, seconds }),
  });
  document.getElementById("taskTitle").value = "";
  refreshTasks();
});

document.getElementById("diagBtn").addEventListener("click", async () => {
  const data = await (await fetch("/api/diagnostics")).json();
  document.getElementById("diagOut").textContent = `${data.result}\n` + (data.checks || []).map((c) => `${c.status} ${c.name}: ${c.detail}`).join("\n");
});

document.getElementById("fileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("fileQuery").value.trim();
  const res = await fetch("/api/files/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();
  const box = document.getElementById("fileList");
  box.innerHTML = "";
  if (!res.ok) {
    box.textContent = data.detail || "ошибка";
    return;
  }
  for (const item of data.items || []) {
    const row = document.createElement("article");
    row.textContent = `${item.name} — ${item.path}`;
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Удалить";
    del.addEventListener("click", async () => {
      if (!(await askConfirm(`Удалить ${item.name}?`))) return;
      const res = await fetch("/api/files/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: item.path, confirm: true }),
      });
      const body = await res.json();
      document.getElementById("toolOut").textContent = body.reply || body.detail || "готово";
    });
    row.appendChild(del);
    box.appendChild(row);
  }
});

document.getElementById("sysBtn").addEventListener("click", async () => {
  const data = await (await fetch("/api/system")).json();
  document.getElementById("toolOut").textContent = data.reply;
});

async function refreshPerms() {
  const data = await (await fetch("/api/permissions")).json();
  const box = document.getElementById("permBox");
  box.innerHTML = "";
  for (const [key, value] of Object.entries(data)) {
    const label = document.createElement("label");
    label.className = "check";
    if (["DELETE_FILES", "RESEARCH", "CAMERA", "SYSTEM_SETTINGS"].includes(key)) {
      label.classList.add("danger");
    }
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    input.addEventListener("change", async () => {
      await fetch("/api/permissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: input.checked }),
      });
    });
    label.appendChild(input);
    label.appendChild(document.createTextNode(` ${key}`));
    box.appendChild(label);
  }
}

document.getElementById("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("researchQuery").value.trim();
  const res = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();
  document.getElementById("researchOut").textContent = data.reply || data.detail || "нет данных";
});

async function refreshLogs() {
  const data = await (await fetch("/api/logs")).json();
  document.getElementById("logBox").textContent = data.text || "";
}
document.getElementById("logRefresh").addEventListener("click", refreshLogs);
document.getElementById("logCopy").addEventListener("click", () => {
  navigator.clipboard.writeText(document.getElementById("logBox").textContent || "").catch(() => {});
});

async function refreshStatus() {
  try {
    const data = await (await fetch("/api/status")).json();
    const pill = document.getElementById("offlinePill");
    if (pill) {
      pill.classList.toggle("hidden", !data.offline);
      pill.hidden = !data.offline;
    }
    if (!busy && !speaking && !listening) {
      setState("idle", data.mode || (data.offline ? "офлайн" : "онлайн"));
    }
  } catch {
    const pill = document.getElementById("offlinePill");
    if (pill) {
      pill.classList.remove("hidden");
      pill.hidden = false;
    }
  }
}

function askConfirm(text) {
  const dlg = document.getElementById("confirmDlg");
  document.getElementById("confirmText").textContent = text;
  dlg.showModal();
  return new Promise((resolve) => {
    const yes = document.getElementById("confirmYes");
    const no = document.getElementById("confirmNo");
    const done = (value) => {
      yes.onclick = null;
      no.onclick = null;
      dlg.close();
      resolve(value);
    };
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
  });
}

async function refreshAgents() {
  const data = await (await fetch("/api/agents")).json();
  const box = document.getElementById("agentList");
  box.innerHTML = "";
  for (const item of data.items || []) {
    const row = document.createElement("article");
    row.textContent = `${item.enabled ? "ON" : "OFF"} · ${item.name} — ${item.instructions}`;
    const run = document.createElement("button");
    run.type = "button";
    run.textContent = "Задача";
    run.addEventListener("click", async () => {
      const query = window.prompt("Задача для агента", "найди и сравни варианты") || "";
      if (!query) return;
      const res = await fetch(`/api/agents/${item.id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const body = await res.json();
      addMessage("assistant", body.reply || body.detail || "готово", body.sources || [], body.steps || []);
      showPage("home");
    });
    const tog = document.createElement("button");
    tog.type = "button";
    tog.textContent = "Вкл/выкл";
    tog.addEventListener("click", async () => {
      await fetch(`/api/agents/${item.id}/toggle`, { method: "POST" });
      refreshAgents();
    });
    row.appendChild(run);
    row.appendChild(tog);
    if (!["Research", "Coding", "File", "System", "Creative", "Testing", "Automation"].includes(item.name) || item.id > 7) {
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Удалить";
      del.addEventListener("click", async () => {
        await fetch(`/api/agents/${item.id}`, { method: "DELETE" });
        refreshAgents();
      });
      row.appendChild(del);
    }
    box.appendChild(row);
  }
}

document.getElementById("agentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("agentName").value.trim();
  if (!name) return;
  await fetch("/api/agents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      role: document.getElementById("agentRole").value.trim(),
      instructions: document.getElementById("agentInstructions").value.trim(),
    }),
  });
  document.getElementById("agentName").value = "";
  document.getElementById("agentRole").value = "";
  document.getElementById("agentInstructions").value = "";
  refreshAgents();
});

document.getElementById("memoryExport").addEventListener("click", async () => {
  const data = await (await fetch("/api/memory-long/export")).json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "nova-memory.json";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("memoryImportBtn").addEventListener("click", () => {
  document.getElementById("memoryImportFile").click();
});
document.getElementById("memoryImportFile").addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const data = JSON.parse(await file.text());
  await fetch("/api/memory-long/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: data.items || [] }),
  });
  refreshMemory();
});
document.getElementById("memoryClear").addEventListener("click", async () => {
  if (!(await askConfirm("Удалить все записи памяти?"))) return;
  const data = await (await fetch("/api/memory-long")).json();
  for (const item of data.items || []) {
    await fetch(`/api/memory-long/${item.id}`, { method: "DELETE" });
  }
  refreshMemory();
});

document.getElementById("fileCreateForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("fileCreateName").value.trim();
  if (!name) return;
  const res = await fetch("/api/files/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, content: "" }),
  });
  const data = await res.json();
  document.getElementById("toolOut").textContent = data.path || data.detail || "готово";
});

document.getElementById("restoreBtn").addEventListener("click", async () => {
  const data = await (await fetch("/api/backups")).json();
  const first = (data.items || [])[0];
  if (!first) {
    document.getElementById("toolOut").textContent = "Резервных копий нет. Сначала сделайте копию.";
    return;
  }
  if (!(await askConfirm(`Восстановить ${first.name}? Текущий профиль будет сохранён.`))) return;
  const res = await fetch("/api/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: first.path }),
  });
  const body = await res.json();
  document.getElementById("toolOut").textContent = body.path || body.detail || "готово";
});

document.getElementById("backupBtn").addEventListener("click", async () => {
  const secrets = await askConfirm("Включить API-ключ в копию? Нет — безопасная копия без секретов.");
  const data = await (await fetch("/api/backup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_secrets: Boolean(secrets) }),
  })).json();
  document.getElementById("toolOut").textContent = `Копия: ${data.path}`;
});

document.getElementById("clearKey").addEventListener("click", async () => {
  await fetch("/api/settings/clear-key", { method: "POST" });
  settings = await (await fetch("/api/settings")).json();
  settingsDlg.close();
});

document.getElementById("wizMic").addEventListener("click", () => {
  const out = document.getElementById("wizProbe");
  if (!SpeechRec) {
    out.textContent = "Микрофон: голосовой ввод доступен в Chrome или Edge. Текстовый режим работает.";
    return;
  }
  const rec = new SpeechRec();
  rec.lang = "ru-RU";
  rec.onresult = (event) => {
    out.textContent = "Микрофон: " + event.results[0][0].transcript;
  };
  rec.onerror = () => {
    out.textContent = "Микрофон недоступен. Можно продолжить текстом.";
  };
  rec.start();
  out.textContent = "Скажите что-нибудь…";
});
document.getElementById("wizVoice").addEventListener("click", () => {
  speak("Я Nova. Голос работает.");
  document.getElementById("wizProbe").textContent = "Проигрываю тестовую фразу.";
});

(async () => {
  try {
    const data = await (await fetch("/api/updates")).json();
    const note = document.getElementById("updateNote");
    if (note) note.textContent = `${data.current}: ${data.note}`;
  } catch { /* ignore */ }
})();
