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
let settings = {};
let audioQueue = Promise.resolve();

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
      .map((s) => `<a href="${s.url}" target="_blank" rel="noreferrer">${s.title || s.url}</a>`)
      .join(" · ");
    wrap.appendChild(src);
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
      audio.onended = () => {
        URL.revokeObjectURL(url);
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
    setState(listening ? "listening" : "idle");
  }
}

async function sendText(text, voiceReply = true) {
  const value = (text || "").trim();
  if (!value) return;
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
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  sendText(inputEl.value, true);
});

function maybeWake(transcript) {
  const t = transcript.trim();
  const lower = t.toLowerCase();
  const woke = /^(нова|nova|джарвис|jarvis)[,.\s:-]*/i.exec(lower);
  if (woke) return t.slice(woke[0].length).trim() || t;
  return t;
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
    if (finalText && !speaking) {
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
      "Я Nova. Работаю как приложение на этом компьютере. Скажите: «открой YouTube», «громче», «пробки Москва», «погода», «курс доллара». Кнопка «Виджет» сворачивает окно.",
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
