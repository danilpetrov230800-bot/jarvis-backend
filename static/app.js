/* Nova — фронтенд персонального ИИ-ассистента */
(() => {
  "use strict";

  const chat = document.getElementById("chat");
  const welcome = document.getElementById("welcome");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("sendBtn");
  const micBtn = document.getElementById("micBtn");
  const ttsBtn = document.getElementById("ttsBtn");
  const clearBtn = document.getElementById("clearBtn");
  const statusEl = document.getElementById("status");
  const statusLabel = document.getElementById("statusLabel");
  const orb = document.getElementById("orb");
  const suggestions = document.getElementById("suggestions");

  /** @type {{role: string, content: string}[]} */
  let history = [];
  let busy = false;
  let ttsOn = false;

  /* ---------- утилиты ---------- */
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Мини-markdown: блоки кода, инлайн-код, жирный/курсив, ссылки, абзацы.
  function renderMarkdown(src) {
    const codeBlocks = [];
    let text = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const i = codeBlocks.length;
      codeBlocks.push(
        `<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`
      );
      return `\u0000CODE${i}\u0000`;
    });

    text = escapeHtml(text);
    text = text.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    text = text.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>'
    );

    const paragraphs = text
      .split(/\n{2,}/)
      .map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`)
      .join("");

    return paragraphs.replace(/\u0000CODE(\d+)\u0000/g, (_, i) => codeBlocks[+i]);
  }

  function scrollToBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  /* ---------- сообщения ---------- */
  function addMessage(role, content) {
    if (welcome && welcome.parentNode) welcome.remove();

    const msg = document.createElement("div");
    msg.className = `msg ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "Ты" : "N";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "user") {
      bubble.innerHTML = renderMarkdown(content);
    }

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chat.appendChild(msg);
    scrollToBottom();
    return bubble;
  }

  function showTyping(bubble) {
    bubble.innerHTML =
      '<div class="typing"><span></span><span></span><span></span></div>';
  }

  /* ---------- отправка ---------- */
  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;

    busy = true;
    setBusy(true);
    input.value = "";
    autoGrow();

    addMessage("user", text);
    history.push({ role: "user", content: text });

    const bubble = addMessage("assistant", "");
    showTyping(bubble);
    orb.classList.add("thinking");

    let full = "";
    let started = false;

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, stream: true }),
      });

      if (!resp.ok || !resp.body) {
        throw new Error("HTTP " + resp.status);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let payload;
          try {
            payload = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }

          if (payload.type === "delta") {
            if (!started) {
              started = true;
              bubble.innerHTML = "";
              bubble.classList.add("cursor-blink");
            }
            full += payload.content;
            bubble.innerHTML = renderMarkdown(full);
            bubble.classList.add("cursor-blink");
            scrollToBottom();
          } else if (payload.type === "error") {
            full += "\n\n⚠️ " + payload.content;
            bubble.innerHTML = renderMarkdown(full);
          } else if (payload.type === "done") {
            bubble.classList.remove("cursor-blink");
          }
        }
      }
    } catch (err) {
      full = full || "⚠️ Не удалось связаться с Nova: " + err.message;
      bubble.innerHTML = renderMarkdown(full);
    } finally {
      bubble.classList.remove("cursor-blink");
      orb.classList.remove("thinking");
      history.push({ role: "assistant", content: full });
      if (ttsOn) speak(full);
      busy = false;
      setBusy(false);
      input.focus();
    }
  }

  function setBusy(state) {
    sendBtn.disabled = state || !input.value.trim();
  }

  /* ---------- озвучка (TTS) ---------- */
  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    const clean = text.replace(/[*`#>_]/g, "").replace(/\n+/g, ". ");
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = "ru-RU";
    u.rate = 1.05;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  /* ---------- голосовой ввод (STT) ---------- */
  let recognition = null;
  function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      micBtn.style.display = "none";
      return;
    }
    recognition = new SR();
    recognition.lang = "ru-RU";
    recognition.interimResults = true;
    recognition.continuous = false;

    let finalText = "";
    recognition.onresult = (e) => {
      let interim = "";
      finalText = "";
      for (let i = 0; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t;
        else interim += t;
      }
      input.value = (finalText || interim).trim();
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
    if (micBtn.classList.contains("recording")) {
      recognition.stop();
    } else {
      try {
        micBtn.classList.add("recording");
        recognition.start();
      } catch {
        micBtn.classList.remove("recording");
      }
    }
  }

  /* ---------- ввод ---------- */
  function autoGrow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  input.addEventListener("input", () => {
    autoGrow();
    setBusy(false);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input.value);
    }
  });

  sendBtn.addEventListener("click", () => send(input.value));
  micBtn.addEventListener("click", toggleMic);

  ttsBtn.addEventListener("click", () => {
    ttsOn = !ttsOn;
    ttsBtn.setAttribute("aria-pressed", String(ttsOn));
    if (!ttsOn && "speechSynthesis" in window) window.speechSynthesis.cancel();
  });

  clearBtn.addEventListener("click", () => {
    history = [];
    chat.innerHTML = "";
    chat.appendChild(welcome);
    if (!welcome.parentNode) chat.appendChild(welcome);
    location.reload();
  });

  suggestions &&
    suggestions.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (chip) send(chip.textContent);
    });

  /* ---------- статус ---------- */
  async function loadStatus() {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      if (d.ai_connected) {
        statusEl.classList.add("online");
        statusLabel.textContent = "ИИ подключён · " + d.model;
      } else {
        statusEl.classList.add("demo");
        statusLabel.textContent = "демо-режим";
      }
    } catch {
      statusLabel.textContent = "оффлайн";
    }
  }

  /* ---------- запуск ---------- */
  initSpeech();
  loadStatus();
  input.focus();
})();
