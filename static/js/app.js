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

function setState(state, detail = "") {
  hud.className = `hud ${state}`;
  hudState.textContent = state.toUpperCase();
  statusLine.textContent = detail || {
    idle: "система в режиме ожидания",
    listening: "слушаю вас, сэр",
    thinking: "анализ запроса",
    speaking: "голосовой канал",
  }[state] || detail;
}

function addMessage(role, text, sources = []) {
  const wrap = document.createElement("article");
  wrap.className = `msg ${role}`;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? (settings.user_name || "Вы") : (settings.assistant_name || "JARVIS");
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
      audioQueue = audioQueue.then(() => speak(data.reply));
      await audioQueue;
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
  const woke = /^(джарвис|jarvis)[,.\s:-]*/i.exec(lower);
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
    addMessage("assistant", "Сэр, голосовой ввод доступен в браузерах Chrome и Edge.");
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
  addMessage("assistant", "Память диалога очищена. Слушаю вас, сэр.");
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
  document.getElementById("assistantName").textContent = settings.assistant_name || "JARVIS";
  settingsDlg.close();
});

async function loadSettingsIntoForm() {
  settings = await (await fetch("/api/settings")).json();
  const form = settingsForm;
  form.provider.value = settings.provider || "auto";
  form.model.value = settings.model || "";
  form.base_url.value = settings.base_url || "";
  form.user_name.value = settings.user_name || "";
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
}

function inferProvider(key) {
  if (key.startsWith("gsk_")) return "groq";
  if (key.startsWith("sk-or-")) return "openrouter";
  if (key.startsWith("sk-")) return "openai";
  return "auto";
}

function isReady(info) {
  return Boolean(info.has_api_key || info.resolved_provider === "ollama");
}

function showSetup(visible) {
  const el = document.getElementById("setup");
  el.hidden = !visible;
  el.classList.toggle("hidden", !visible);
}

document.getElementById("setupSave").addEventListener("click", async () => {
  const key = document.getElementById("setupKey").value.trim();
  const name = document.getElementById("setupName").value.trim() || "Данила";
  const err = document.getElementById("setupError");
  if (!key) {
    err.hidden = false;
    err.textContent = "Вставьте ключ — без него модель не ответит.";
    return;
  }
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: key, user_name: name, provider: inferProvider(key) }),
  });
  if (!res.ok) {
    err.hidden = false;
    err.textContent = "Не удалось сохранить ключ.";
    return;
  }
  settings = await (await fetch("/api/settings")).json();
  showSetup(false);
  addMessage("assistant", `Системы в норме. Я ${settings.assistant_name}, ${name}. Можно говорить или писать.`);
  setState("idle", "онлайн");
});

async function boot() {
  setupMic();
  try {
    settings = await (await fetch("/api/settings")).json();
    document.getElementById("assistantName").textContent = settings.assistant_name || "JARVIS";
    if (!isReady(settings)) {
      showSetup(true);
      setState("idle", "нужен API-ключ");
      return;
    }
    addMessage(
      "assistant",
      `Системы в норме. Я ${settings.assistant_name}, сэр. Можно говорить или писать — при необходимости я сам полезу в сеть.`,
    );
    setState("idle", "онлайн");
  } catch {
    addMessage("assistant", "Не удалось связаться с локальным ядром JARVIS.");
  }
}

boot();
