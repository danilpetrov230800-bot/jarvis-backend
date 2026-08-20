const $ = (selector) => document.querySelector(selector);
const conversation = $("#conversation");
const hero = $("#hero");
const messages = $("#messages");
const form = $("#chatForm");
const promptInput = $("#prompt");
const sendButton = $("#sendButton");
const settingsDialog = $("#settingsDialog");

const state = {
  history: JSON.parse(localStorage.getItem("nova-history") || "[]").slice(-30),
  model: localStorage.getItem("nova-model") || "qwen2.5:7b",
  speak: localStorage.getItem("nova-speak") === "true",
  busy: false,
};

function saveHistory() {
  localStorage.setItem("nova-history", JSON.stringify(state.history.slice(-30)));
}

function setPresence(online, label, model) {
  ["#sidebarDot", "#headerDot"].forEach((selector) => {
    $(selector).className = `status-dot ${online ? "online" : "error"}`;
  });
  $("#sidebarStatus").textContent = online ? "Система онлайн" : "Модель не запущена";
  $("#headerStatus").textContent = label;
  $("#modelLabel").textContent = model || "Ollama";
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Не удалось выполнить запрос.");
  return payload;
}

async function refreshStatus() {
  try {
    const status = await request("/api/status");
    setPresence(
      status.online,
      status.online ? `Nova активна · ${state.model}` : "Ollama не отвечает",
      state.model,
    );
    $("#models").replaceChildren(
      ...status.models.map((model) => {
        const option = document.createElement("option");
        option.value = model;
        return option;
      }),
    );
  } catch {
    setPresence(false, "Сервис Nova недоступен", state.model);
  }
}

function createMessage(role, content, options = {}) {
  hero.hidden = true;
  messages.classList.add("visible");

  const article = document.createElement("article");
  article.className = `message ${role}${options.thinking ? " thinking" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "assistant" ? "N" : "D";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const header = document.createElement("header");
  header.textContent = role === "assistant" ? "NOVA" : "ВЫ";
  const body = document.createElement("div");
  body.className = "content";
  body.textContent = content;
  bubble.append(header, body);
  article.append(avatar, bubble);
  messages.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

function renderCommand(proposal, parent) {
  const card = document.createElement("section");
  card.className = "command-card";

  const head = document.createElement("div");
  head.className = "command-head";
  const type = document.createElement("span");
  type.textContent = "КОМАНДА ТЕРМИНАЛА";
  const risk = document.createElement("span");
  risk.className = `risk ${proposal.risk}`;
  risk.textContent = { normal: "обычный риск", elevated: "повышенный риск", critical: "критический риск" }[proposal.risk];
  head.append(type, risk);

  const code = document.createElement("pre");
  code.textContent = proposal.command;
  const actions = document.createElement("div");
  actions.className = "command-actions";
  const run = document.createElement("button");
  run.className = "run-command";
  run.textContent = "Подтвердить и запустить";
  const cancel = document.createElement("button");
  cancel.className = "cancel-command";
  cancel.textContent = "Отмена";
  actions.append(run, cancel);
  card.append(head, code, actions);
  parent.querySelector(".bubble").append(card);

  cancel.addEventListener("click", () => {
    actions.remove();
    risk.textContent = "отменено";
  });

  run.addEventListener("click", async () => {
    run.disabled = true;
    run.textContent = "Выполняю...";
    try {
      const result = await request("/api/commands/execute", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: proposal.proposal_id,
          confirmed: true,
          timeout: 60,
        }),
      });
      actions.remove();
      risk.textContent = result.exit_code === 0 ? `готово · ${result.duration_ms} мс` : `код ${result.exit_code}`;
      risk.className = `risk ${result.exit_code === 0 ? "" : "critical"}`;
      const output = document.createElement("pre");
      output.className = "command-output";
      output.textContent = result.output || "(команда не вернула вывод)";
      card.append(output);
    } catch (error) {
      run.disabled = false;
      run.textContent = "Повторить";
      const output = document.createElement("pre");
      output.className = "command-output";
      output.textContent = error.message;
      card.append(output);
    }
    conversation.scrollTop = conversation.scrollHeight;
  });
}

function speak(text) {
  if (!state.speak || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ru-RU";
  utterance.rate = 1.03;
  speechSynthesis.speak(utterance);
}

async function sendMessage(rawText) {
  const text = rawText.trim();
  if (!text || state.busy) return;

  state.busy = true;
  sendButton.disabled = true;
  promptInput.value = "";
  resizeInput();
  createMessage("user", text);
  const thinking = createMessage("assistant", "", { thinking: true });

  try {
    let reply;
    let command;
    if (text.startsWith("/run ")) {
      command = await request("/api/commands/prepare", {
        method: "POST",
        body: JSON.stringify({ command: text.slice(5).trim() }),
      });
      reply = "Команда подготовлена. Проверьте её перед локальным запуском.";
    } else {
      const result = await request("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          history: state.history.slice(-20),
          model: state.model,
        }),
      });
      reply = result.reply || "Готово.";
      command = result.command;
    }

    thinking.remove();
    const answer = createMessage("assistant", reply);
    if (command) renderCommand(command, answer);
    state.history.push({ role: "user", content: text }, { role: "assistant", content: reply });
    saveHistory();
    speak(reply);
  } catch (error) {
    thinking.remove();
    createMessage("assistant", `Не удалось ответить: ${error.message}`);
  } finally {
    state.busy = false;
    sendButton.disabled = false;
    promptInput.focus();
  }
}

function resizeInput() {
  promptInput.style.height = "auto";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 140)}px`;
}

function resetChat() {
  state.history = [];
  saveHistory();
  messages.replaceChildren();
  messages.classList.remove("visible");
  hero.hidden = false;
  promptInput.focus();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(promptInput.value);
});

promptInput.addEventListener("input", resizeInput);
promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});

$("#newChat").addEventListener("click", resetChat);
$("#clearChat").addEventListener("click", resetChat);
$("#commandMode").addEventListener("click", () => {
  promptInput.value = promptInput.value.startsWith("/run ") ? promptInput.value.slice(5) : `/run ${promptInput.value}`;
  $("#commandMode").classList.toggle("active", promptInput.value.startsWith("/run "));
  promptInput.focus();
});

$("#openSettings").addEventListener("click", () => {
  $("#modelInput").value = state.model;
  $("#speechToggle").checked = state.speak;
  settingsDialog.showModal();
});

$("#modelInput").addEventListener("input", (event) => {
  $("#pullCommand").textContent = `ollama pull ${event.target.value || "qwen2.5:7b"}`;
});

$("#saveSettings").addEventListener("click", () => {
  state.model = $("#modelInput").value.trim() || "qwen2.5:7b";
  state.speak = $("#speechToggle").checked;
  localStorage.setItem("nova-model", state.model);
  localStorage.setItem("nova-speak", state.speak);
  refreshStatus();
});

$("#mobileMenu").addEventListener("click", () => $(".sidebar").classList.toggle("open"));

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  const recognition = new SpeechRecognition();
  recognition.lang = "ru-RU";
  recognition.interimResults = false;
  recognition.addEventListener("start", () => $("#voiceButton").classList.add("listening"));
  recognition.addEventListener("end", () => $("#voiceButton").classList.remove("listening"));
  recognition.addEventListener("result", (event) => {
    promptInput.value = event.results[0][0].transcript;
    resizeInput();
    promptInput.focus();
  });
  $("#voiceButton").addEventListener("click", () => recognition.start());
} else {
  $("#voiceButton").disabled = true;
  $("#voiceButton").title = "Голосовой ввод не поддерживается браузером";
}

if (state.history.length) {
  state.history.forEach((item) => createMessage(item.role, item.content));
}
$("#modelInput").value = state.model;
$("#speechToggle").checked = state.speak;
refreshStatus();
