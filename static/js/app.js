/**
 * NOVA Desktop Frontend Logic
 */
document.addEventListener("DOMContentLoaded", () => {
  // Navigation & Tabs
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const pageTitle = document.getElementById("pageTitle");

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      navItems.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPane = document.getElementById(`pane-${tab}`);
      if (targetPane) targetPane.classList.add("active");
      pageTitle.textContent = btn.querySelector("span:last-child").textContent;

      if (tab === "memory") loadMemory();
      if (tab === "skills") loadSkills();
      if (tab === "agents") loadAgents();
      if (tab === "tools") loadSystemMetrics();
      if (tab === "logs") loadLogs();
      if (tab === "settings") loadSettings();
    });
  });

  // Chat and Voice
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSend");
  const chatMessages = document.getElementById("chatMessages");
  const btnMic = document.getElementById("btnMic");

  async function sendMessage(text, source = "text") {
    const msg = text || chatInput.value.trim();
    if (!msg) return;

    appendMessage("user", msg);
    if (!text) chatInput.value = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, source }),
      });
      const data = await res.json();
      appendMessage("assistant", data.reply || "Ответ получен.");

      // If voice enabled, synthesize speech
      if (data.reply) {
        speakResponse(data.reply);
      }
    } catch (e) {
      appendMessage("assistant", "Произошла ошибка связи с локальным сервером NOVA.");
    }
  }

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const avatar = role === "user" ? "👤" : "✦";
    const title = role === "user" ? "Вы" : "NOVA Assistant";
    div.innerHTML = `
      <div class="avatar">${avatar}</div>
      <div class="msg-body">
        <div class="msg-header">${title}</div>
        <div class="msg-text">${escapeHtml(text)}</div>
      </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  btnSend.addEventListener("click", () => sendMessage());
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Web Speech & Wake Word STT
  let recognition = null;
  let isListening = false;
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "ru-RU";

    recognition.onresult = (event) => {
      const transcript = event.results[event.results.length - 1][0].transcript.trim();
      sendMessage(transcript, "voice");
    };

    recognition.onerror = () => {
      btnMic.classList.remove("active");
      isListening = false;
    };
  }

  btnMic.addEventListener("click", () => {
    if (!recognition) {
      alert("Распознавание речи не поддерживается браузером.");
      return;
    }
    if (!isListening) {
      recognition.start();
      btnMic.classList.add("active");
      isListening = true;
    } else {
      recognition.stop();
      btnMic.classList.remove("active");
      isListening = false;
    }
  });

  async function speakResponse(text) {
    try {
      const res = await fetch("/api/voice/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        audio.play();
      }
    } catch (e) {
      // Fallback
    }
  }

  // Multi-Agent loading
  async function loadAgents() {
    const grid = document.getElementById("agentsGrid");
    try {
      const res = await fetch("/api/agents");
      const agents = await res.json();
      grid.innerHTML = agents
        .map(
          (a) => `
        <div class="agent-card">
          <div class="skill-card-header">
            <span class="skill-title">${escapeHtml(a.name)}</span>
            <span class="tag">${a.is_system ? "System Agent" : "Custom"}</span>
          </div>
          <p style="font-size: 12.5px; color: var(--text-muted);">${escapeHtml(a.role)}</p>
          <div style="margin-top: 8px;">
            <button class="btn-secondary" onclick="runAgentPrompt('${a.id}')">Запустить задачу</button>
          </div>
        </div>
      `
        )
        .join("");
    } catch (e) {}
  }

  window.runAgentPrompt = async (agentId) => {
    const prompt = window.prompt("Введите задачу для агента:");
    if (!prompt) return;
    const viz = document.getElementById("agentVisualizer");
    viz.style.display = "block";
    document.getElementById("vizStatus").textContent = "Выполнение...";

    try {
      const res = await fetch("/api/agents/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, task_prompt: prompt }),
      });
      const data = await res.json();
      document.getElementById("vizStatus").textContent = data.success ? "Завершено" : "Ошибка";
      const stepsDiv = document.getElementById("vizSteps");
      stepsDiv.innerHTML = data.steps
        .map(
          (s) => `
        <div class="viz-step-item">
          <span>${s.status === "completed" ? "✅" : "⚠️"}</span>
          <span>Шаг ${s.step}: ${escapeHtml(s.name)}</span>
        </div>
      `
        )
        .join("");
      appendMessage("assistant", data.summary);
    } catch (e) {
      alert("Ошибка запуска агента: " + e.message);
    }
  };

  // Skills loading
  async function loadSkills() {
    const list = document.getElementById("skillsList");
    try {
      const res = await fetch("/api/skills");
      const skills = await res.json();
      list.innerHTML = skills
        .map(
          (s) => `
        <div class="skill-card">
          <div class="skill-card-header">
            <span class="skill-title">${escapeHtml(s.name)}</span>
            <span class="tag">Триггер: «${escapeHtml(s.trigger_value)}»</span>
          </div>
          <p style="font-size: 12.5px; color: var(--text-muted);">${escapeHtml(s.description)}</p>
          <div style="margin-top: 8px;">
            <button class="btn-secondary" onclick="runSkillAction('${s.id}')">Тестовый запуск</button>
          </div>
        </div>
      `
        )
        .join("");
    } catch (e) {}
  }

  window.runSkillAction = async (skillId) => {
    try {
      const res = await fetch(`/api/skills/${skillId}/run`, { method: "POST" });
      const data = await res.json();
      alert(`Навык выполнен! Шагов: ${data.steps_executed}`);
    } catch (e) {
      alert("Ошибка: " + e.message);
    }
  };

  // Memory loading
  async function loadMemory() {
    const grid = document.getElementById("memoryGrid");
    try {
      const res = await fetch("/api/memory");
      const memories = await res.json();
      grid.innerHTML = memories
        .map(
          (m) => `
        <div class="memory-card">
          <div class="skill-card-header">
            <span class="skill-title">${escapeHtml(m.title)}</span>
            <span class="tag">${m.category}</span>
          </div>
          <p style="font-size: 13px;">${escapeHtml(m.content)}</p>
        </div>
      `
        )
        .join("");
    } catch (e) {}
  }

  // System Metrics
  async function loadSystemMetrics() {
    try {
      const res = await fetch("/api/tools/system/metrics");
      const data = await res.json();
      document.getElementById("metricCpu").textContent = `${data.cpu.percent}%`;
      document.getElementById("metricRam").textContent = `${data.memory.percent}%`;
      document.getElementById("metricDisk").textContent = `${data.main_disk.percent}%`;
    } catch (e) {}
  }

  document.getElementById("btnRefreshMetrics")?.addEventListener("click", loadSystemMetrics);

  // Diagnostics
  document.getElementById("btnRunDiagnostics")?.addEventListener("click", async () => {
    const list = document.getElementById("diagChecksList");
    const badge = document.getElementById("diagStatusBadge");
    badge.textContent = "Выполняется тестирование подсистем...";

    try {
      const res = await fetch("/api/diagnostics/run");
      const data = await res.json();
      badge.textContent = `Статус: ${data.overall_status} (Время: ${data.duration_ms} мс)`;
      list.innerHTML = data.checks
        .map(
          (c) => `
        <div class="diag-item">
          <div>
            <strong>${escapeHtml(c.name)}</strong>
            <p style="font-size: 12px; color: var(--text-muted);">${escapeHtml(c.message)}</p>
          </div>
          <span class="diag-status-${c.status.toLowerCase()}">${c.status}</span>
        </div>
      `
        )
        .join("");
    } catch (e) {
      badge.textContent = "Ошибка запуска самодиагностики";
    }
  });

  // Settings
  async function loadSettings() {
    try {
      const res = await fetch("/api/settings");
      const cfg = await res.json();
      document.getElementById("cfgAiProvider").value = cfg.ai.provider;
      document.getElementById("cfgApiKey").value = cfg.ai.api_key || "";
      document.getElementById("cfgAiModel").value = cfg.ai.model || "gpt-4o-mini";
      document.getElementById("cfgVoiceEnabled").checked = cfg.voice.enabled;
      document.getElementById("cfgWakeWordEnabled").checked = cfg.voice.wake_word_enabled;
    } catch (e) {}
  }

  document.getElementById("btnSaveSettings")?.addEventListener("click", async () => {
    const newSettings = {
      ai: {
        provider: document.getElementById("cfgAiProvider").value,
        api_key: document.getElementById("cfgApiKey").value,
        model: document.getElementById("cfgAiModel").value,
      },
      voice: {
        enabled: document.getElementById("cfgVoiceEnabled").checked,
        wake_word_enabled: document.getElementById("cfgWakeWordEnabled").checked,
      },
      security: {
        allow_file_read: document.getElementById("cfgAllowFileRead").checked,
        allow_file_write: document.getElementById("cfgAllowFileWrite").checked,
        allow_file_delete: document.getElementById("cfgAllowFileDelete").checked,
        allow_app_launch: document.getElementById("cfgAllowAppLaunch").checked,
        allow_system_control: document.getElementById("cfgAllowSystemControl").checked,
        require_confirmation_for_dangerous: document.getElementById("cfgRequireConfirm").checked,
      },
    };

    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSettings),
      });
      alert("Настройки успешно сохранены!");
    } catch (e) {
      alert("Ошибка сохранения: " + e.message);
    }
  });

  // Theme toggle
  document.getElementById("btnThemeToggle")?.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
  });

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
