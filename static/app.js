/* Nova — фронтенд персонального ИИ-ассистента */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const chat = $("chat");
  const welcome = $("welcome");
  const input = $("input");
  const sendBtn = $("sendBtn");
  const micBtn = $("micBtn");
  const ttsBtn = $("ttsBtn");
  const clearBtn = $("clearBtn");
  const statusEl = $("status");
  const statusLabel = $("statusLabel");
  const orb = $("orb");
  const suggestions = $("suggestions");
  const sysBtn = $("sysBtn");
  const sysPanel = $("sysPanel");
  const sysClose = $("sysClose");
  const widgetBtn = $("widgetBtn");
  const installBtn = $("installBtn");

  const TOOL_ICONS = {
    weather: "🌤", web_search: "🔎", wikipedia: "📚", currency: "💱",
    time: "🕐", route: "🗺", news: "📰", calculate: "🧮", system: "🖥",
  };

  let history = [];
  let busy = false;
  let ttsOn = false;

  /* ---------- utils ---------- */
  const escapeHtml = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function renderMarkdown(src) {
    const code = [];
    let t = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, l, c) => {
      code.push(`<pre><code>${escapeHtml(c.replace(/\n$/, ""))}</code></pre>`);
      return `\u0000C${code.length - 1}\u0000`;
    });
    t = escapeHtml(t);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    t = t.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    t = t.split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
    return t.replace(/\u0000C(\d+)\u0000/g, (_, i) => code[+i]);
  }

  const scrollDown = () => (chat.scrollTop = chat.scrollHeight);

  function addMessage(role) {
    if (welcome && welcome.parentNode) welcome.remove();
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "Ты" : "N";
    const content = document.createElement("div");
    content.className = "content";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    content.appendChild(bubble);
    msg.appendChild(avatar);
    msg.appendChild(content);
    chat.appendChild(msg);
    scrollDown();
    return { msg, content, bubble };
  }

  function addToolCard(content, ev) {
    const card = document.createElement("div");
    card.className = "tool-card" + (ev.ok === false ? " err" : "");
    const ico = TOOL_ICONS[ev.tool] || "🛠";
    card.innerHTML =
      `<span class="tool-ico">${ico}</span><span>${escapeHtml(ev.title || ev.tool)}</span>` +
      (ev.source ? `<span class="tool-src">${escapeHtml(ev.source)}</span>` : "");
    content.insertBefore(card, content.lastChild);
    scrollDown();
  }

  /* ---------- send ---------- */
  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    setBusy(true);
    input.value = "";
    autoGrow();

    const u = addMessage("user");
    u.bubble.innerHTML = renderMarkdown(text);
    history.push({ role: "user", content: text });

    const a = addMessage("assistant");
    a.bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    orb.classList.add("thinking");

    let full = "", started = false;
    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, stream: true }),
      });
      if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);

      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let p;
          try { p = JSON.parse(line.slice(5).trim()); } catch { continue; }

          if (p.type === "tool") {
            addToolCard(a.content, p);
          } else if (p.type === "delta") {
            if (!started) { started = true; a.bubble.innerHTML = ""; }
            full += p.content;
            a.bubble.innerHTML = renderMarkdown(full);
            a.bubble.classList.add("cursor-blink");
            scrollDown();
          } else if (p.type === "error") {
            full += "\n\n⚠️ " + p.content;
            a.bubble.innerHTML = renderMarkdown(full);
          } else if (p.type === "done") {
            a.bubble.classList.remove("cursor-blink");
          }
        }
      }
    } catch (err) {
      full = full || "⚠️ Не удалось связаться с Nova: " + err.message;
      a.bubble.innerHTML = renderMarkdown(full);
    } finally {
      a.bubble.classList.remove("cursor-blink");
      orb.classList.remove("thinking");
      history.push({ role: "assistant", content: full });
      if (ttsOn) speak(full);
      busy = false;
      setBusy(false);
      input.focus();
    }
  }

  const setBusy = (s) => (sendBtn.disabled = s || !input.value.trim());

  /* ---------- TTS / STT ---------- */
  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text.replace(/[*`#>_]/g, "").replace(/\n+/g, ". "));
    u.lang = "ru-RU";
    u.rate = 1.05;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  }

  let recognition = null;
  function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { micBtn.style.display = "none"; return; }
    recognition = new SR();
    recognition.lang = "ru-RU";
    recognition.interimResults = true;
    recognition.onresult = (e) => {
      let s = "";
      for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript;
      input.value = s.trim();
      autoGrow();
      setBusy(false);
    };
    recognition.onend = () => {
      micBtn.classList.remove("recording");
      if (input.value.trim()) send(input.value);
    };
    recognition.onerror = () => micBtn.classList.remove("recording");
  }
  function toggleMic() {
    if (!recognition) return;
    if (micBtn.classList.contains("recording")) recognition.stop();
    else { try { micBtn.classList.add("recording"); recognition.start(); } catch { micBtn.classList.remove("recording"); } }
  }

  /* ---------- input ---------- */
  function autoGrow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }
  input.addEventListener("input", () => { autoGrow(); setBusy(false); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  sendBtn.addEventListener("click", () => send(input.value));
  micBtn.addEventListener("click", toggleMic);
  ttsBtn.addEventListener("click", () => {
    ttsOn = !ttsOn;
    ttsBtn.setAttribute("aria-pressed", String(ttsOn));
    if (!ttsOn && "speechSynthesis" in window) speechSynthesis.cancel();
  });
  clearBtn.addEventListener("click", () => location.reload());
  suggestions && suggestions.addEventListener("click", (e) => {
    const c = e.target.closest(".chip");
    if (c) send(c.textContent);
  });

  /* ---------- system panel ---------- */
  async function api(path, opts) {
    const r = await fetch(path, opts);
    return r.json();
  }
  function sysNote(msg) { $("sysNote").textContent = msg || ""; }

  async function loadSysStatus() {
    try {
      const d = await api("/api/system/status");
      $("sysStatus").textContent = d.ok ? `🖥 ${d.message}` : "Статус недоступен";
    } catch { $("sysStatus").textContent = "Статус недоступен"; }
  }
  sysBtn.addEventListener("click", () => {
    sysPanel.classList.add("open");
    sysPanel.setAttribute("aria-hidden", "false");
    loadSysStatus();
    api("/api/system/volume").then((d) => { if (d.ok) { $("volume").value = d.volume; $("volVal").textContent = d.volume + "%"; } });
  });
  sysClose.addEventListener("click", () => { sysPanel.classList.remove("open"); sysPanel.setAttribute("aria-hidden", "true"); });
  $("sysRefresh").addEventListener("click", loadSysStatus);

  let volT, brT;
  $("volume").addEventListener("input", (e) => {
    $("volVal").textContent = e.target.value + "%";
    clearTimeout(volT);
    volT = setTimeout(async () => {
      const d = await api("/api/system/volume", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ value: +e.target.value }) });
      sysNote(d.ok ? "" : d.message);
    }, 250);
  });
  $("brightness").addEventListener("input", (e) => {
    $("brVal").textContent = e.target.value + "%";
    clearTimeout(brT);
    brT = setTimeout(async () => {
      const d = await api("/api/system/brightness", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ value: +e.target.value }) });
      sysNote(d.ok ? "" : d.message);
    }, 250);
  });
  let muted = false;
  sysPanel.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.media) {
      const d = await api("/api/system/media", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: b.dataset.media }) });
      sysNote(d.message);
    } else if (b.dataset.mute) {
      muted = !muted;
      const d = await api("/api/system/mute", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: muted }) });
      sysNote(d.message);
    } else if (b.dataset.power) {
      const d = await api("/api/system/power", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: b.dataset.power }) });
      sysNote(d.message);
    }
  });

  /* ---------- widget mode + drag ---------- */
  const app = $("app");
  widgetBtn.addEventListener("click", () => {
    const on = document.body.classList.toggle("widget");
    widgetBtn.title = on ? "Развернуть" : "Свернуть в виджет";
    if (!on) { app.style.left = app.style.top = app.style.right = app.style.bottom = ""; }
  });
  let drag = null;
  $("topbar").addEventListener("pointerdown", (e) => {
    if (!document.body.classList.contains("widget")) return;
    if (e.target.closest("button")) return;
    const r = app.getBoundingClientRect();
    drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    app.setPointerCapture?.(e.pointerId);
  });
  $("topbar").addEventListener("pointermove", (e) => {
    if (!drag) return;
    app.style.right = "auto"; app.style.bottom = "auto";
    app.style.left = Math.max(0, e.clientX - drag.dx) + "px";
    app.style.top = Math.max(0, e.clientY - drag.dy) + "px";
  });
  const stopDrag = () => (drag = null);
  $("topbar").addEventListener("pointerup", stopDrag);
  $("topbar").addEventListener("pointercancel", stopDrag);

  /* ---------- PWA ---------- */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  let deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBtn.hidden = false;
  });
  installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    installBtn.hidden = true;
  });

  /* ---------- status ---------- */
  async function loadStatus() {
    try {
      const d = await api("/api/health");
      if (d.provider === "demo") { statusEl.classList.add("demo"); statusLabel.textContent = "демо-режим"; }
      else { statusEl.classList.add("online"); statusLabel.textContent = (d.provider_label || d.provider) + " · " + d.model; }
    } catch { statusLabel.textContent = "оффлайн"; }
  }

  initSpeech();
  loadStatus();
  input.focus();
})();
