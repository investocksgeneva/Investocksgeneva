const setupScreen = document.getElementById("setupScreen");
const chatScreen = document.getElementById("chatScreen");
const setupForm = document.getElementById("setupForm");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const messagesEl = document.getElementById("messages");
const newScenarioBtn = document.getElementById("newScenarioBtn");
const endBtn = document.getElementById("endBtn");
const feedbackPanel = document.getElementById("feedbackPanel");
const micBtn = document.getElementById("micBtn");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");
const scenarioNameInput = document.getElementById("scenarioName");
const savedScenariosSection = document.getElementById("savedScenarios");
const savedScenariosList = document.getElementById("savedScenariosList");
const lastTimeNote = document.getElementById("lastTimeNote");
const retryBtn = document.getElementById("retryBtn");

let state = {
  system: "",
  feedbackSystem: "",
  messages: [], // {role: 'user'|'assistant', content: string}
  scenarioId: null, // saved scenario this session belongs to, if any
};

// ---- Scenario storage (Phase 3) -----------------------------------------

const SCENARIOS_KEY = "articulations_scenarios";

function makeId() {
  if (window.crypto?.randomUUID) return crypto.randomUUID();
  return `s_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function loadScenarios() {
  try {
    return JSON.parse(localStorage.getItem(SCENARIOS_KEY)) || [];
  } catch {
    return [];
  }
}

function saveScenarios(list) {
  localStorage.setItem(SCENARIOS_KEY, JSON.stringify(list));
}

function upsertScenario({ name, situation, otherPerson, yourGoal, difficulty }) {
  const list = loadScenarios();
  let scenario = list.find((s) => s.name.toLowerCase() === name.toLowerCase());
  if (!scenario) {
    scenario = { id: makeId(), name, sessions: [] };
    list.push(scenario);
  }
  Object.assign(scenario, { name, situation, otherPerson, yourGoal, difficulty, updatedAt: new Date().toISOString() });
  saveScenarios(list);
  return scenario;
}

function appendSession(scenarioId, feedback) {
  const list = loadScenarios();
  const scenario = list.find((s) => s.id === scenarioId);
  if (!scenario) return;
  scenario.sessions = scenario.sessions || [];
  scenario.sessions.push({ date: new Date().toISOString(), feedback });
  scenario.sessions = scenario.sessions.slice(-5);
  saveScenarios(list);
}

function deleteScenario(id) {
  saveScenarios(loadScenarios().filter((s) => s.id !== id));
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function renderSavedScenarios() {
  const list = loadScenarios().sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  savedScenariosSection.hidden = list.length === 0;
  savedScenariosList.innerHTML = "";

  for (const scenario of list) {
    const item = document.createElement("div");
    item.className = "saved-scenario-item";

    const info = document.createElement("div");
    info.className = "info";
    const nameEl = document.createElement("div");
    nameEl.className = "name";
    nameEl.textContent = scenario.name;
    const lastPracticed = document.createElement("div");
    lastPracticed.className = "last-practiced";
    const lastSession = scenario.sessions?.[scenario.sessions.length - 1];
    lastPracticed.textContent = lastSession ? `Last practiced ${formatDate(lastSession.date)}` : "Not practiced yet";
    info.append(nameEl, lastPracticed);

    const loadBtn = document.createElement("button");
    loadBtn.textContent = "Load";
    loadBtn.addEventListener("click", () => loadScenarioIntoForm(scenario));

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "Delete";
    deleteBtn.className = "delete-btn";
    deleteBtn.addEventListener("click", () => {
      if (confirm(`Delete "${scenario.name}"? This can't be undone.`)) {
        deleteScenario(scenario.id);
        renderSavedScenarios();
      }
    });

    item.append(info, loadBtn, deleteBtn);
    savedScenariosList.appendChild(item);
  }
}

function loadScenarioIntoForm(scenario) {
  scenarioNameInput.value = scenario.name;
  document.getElementById("situation").value = scenario.situation;
  document.getElementById("otherPerson").value = scenario.otherPerson;
  document.getElementById("yourGoal").value = scenario.yourGoal || "";
  document.getElementById("difficulty").value = scenario.difficulty || "";

  const lastSession = scenario.sessions?.[scenario.sessions.length - 1];
  if (lastSession) {
    lastTimeNote.hidden = false;
    const excerpt = lastSession.feedback.length > 220 ? lastSession.feedback.slice(0, 220) + "…" : lastSession.feedback;
    lastTimeNote.innerHTML = `<strong>Last practiced ${formatDate(lastSession.date)}:</strong> ${excerpt}`;
  } else {
    lastTimeNote.hidden = true;
  }
  document.getElementById("situation").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- Voice (Phase 2) ----------------------------------------------------

const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
const speechSupported = !!SpeechRecognitionImpl;
const ttsSupported = "speechSynthesis" in window;

let recognition = null;
let listening = false;
let voiceRepliesEnabled = localStorage.getItem("articulations_voice_replies") === "true";

if (speechSupported) {
  micBtn.hidden = false;
  recognition = new SpeechRecognitionImpl();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.addEventListener("result", (e) => {
    const transcript = e.results[0]?.[0]?.transcript?.trim();
    if (transcript) {
      chatInput.value = transcript;
      autoGrow(chatInput);
      chatForm.requestSubmit();
    }
  });

  recognition.addEventListener("end", () => {
    listening = false;
    micBtn.setAttribute("aria-pressed", "false");
  });

  recognition.addEventListener("error", () => {
    listening = false;
    micBtn.setAttribute("aria-pressed", "false");
  });
}

if (ttsSupported) {
  voiceToggleBtn.hidden = false;
  voiceToggleBtn.setAttribute("aria-pressed", String(voiceRepliesEnabled));
}

micBtn?.addEventListener("click", () => {
  if (!recognition) return;
  if (listening) {
    recognition.stop();
    return;
  }
  window.speechSynthesis?.cancel();
  try {
    recognition.start();
    listening = true;
    micBtn.setAttribute("aria-pressed", "true");
  } catch {
    // already started; ignore
  }
});

voiceToggleBtn?.addEventListener("click", () => {
  voiceRepliesEnabled = !voiceRepliesEnabled;
  localStorage.setItem("articulations_voice_replies", String(voiceRepliesEnabled));
  voiceToggleBtn.setAttribute("aria-pressed", String(voiceRepliesEnabled));
  if (!voiceRepliesEnabled) window.speechSynthesis?.cancel();
});

function speak(text) {
  if (!ttsSupported || !voiceRepliesEnabled) return;
  const spoken = text.replace(/\*[^*]*\*/g, "").trim();
  if (!spoken) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(spoken);
  window.speechSynthesis.speak(utterance);
}

function resetToSetup() {
  window.speechSynthesis?.cancel();
  if (listening) recognition?.stop();
  state = { system: "", feedbackSystem: "", messages: [], scenarioId: null };
  messagesEl.innerHTML = "";
  feedbackPanel.hidden = true;
  feedbackPanel.textContent = "";
  lastTimeNote.hidden = true;
  setupScreen.hidden = false;
  chatScreen.hidden = true;
  newScenarioBtn.hidden = true;
  setupForm.reset();
  updateRetryVisibility();
  renderSavedScenarios();
}

function updateRetryVisibility() {
  retryBtn.hidden = !state.messages.some((m) => m.role === "user");
}

function retryLastLine() {
  const sendBtn = chatForm.querySelector("button[type=submit]");
  if (sendBtn.disabled) return; // request in flight

  let lastUserIdx = -1;
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i].role === "user") {
      lastUserIdx = i;
      break;
    }
  }
  if (lastUserIdx === -1) return;

  const userText = state.messages[lastUserIdx].content;
  state.messages.length = lastUserIdx;
  messagesEl.querySelectorAll("[data-msg-index]").forEach((el) => {
    if (Number(el.dataset.msgIndex) >= lastUserIdx) el.remove();
  });
  document.querySelectorAll(".bubble.pending, .bubble.error").forEach((el) => el.remove());

  window.speechSynthesis?.cancel();
  chatInput.value = userText;
  autoGrow(chatInput);
  chatInput.focus();
  updateRetryVisibility();
}

retryBtn.addEventListener("click", retryLastLine);
renderSavedScenarios();

function addBubble(role, text, extraClass = "") {
  const div = document.createElement("div");
  div.className = `bubble ${role === "user" ? "user" : "other"} ${extraClass}`.trim();
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

chatInput.addEventListener("input", () => autoGrow(chatInput));

setupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const situation = document.getElementById("situation").value.trim();
  const otherPerson = document.getElementById("otherPerson").value.trim();
  const yourGoal = document.getElementById("yourGoal").value.trim();
  const difficulty = document.getElementById("difficulty").value;
  const scenarioName = scenarioNameInput.value.trim();

  const submitBtn = setupForm.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "Setting up…";

  try {
    const res = await fetch("/api/system", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ situation, otherPerson, yourGoal, difficulty }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to start scenario.");

    state.system = data.system;
    state.feedbackSystem = data.feedbackSystem;
    state.messages = [];
    state.scenarioId = scenarioName
      ? upsertScenario({ name: scenarioName, situation, otherPerson, yourGoal, difficulty }).id
      : null;

    setupScreen.hidden = true;
    chatScreen.hidden = false;
    newScenarioBtn.hidden = false;
    messagesEl.innerHTML = "";
    feedbackPanel.hidden = true;
    updateRetryVisibility();

    addBubble("other", "Ready when you are — say your opening line.", "pending");
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Start rehearsal";
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;

  document.querySelectorAll(".bubble.pending").forEach((el) => el.remove());

  const userBubble = addBubble("user", text);
  state.messages.push({ role: "user", content: text });
  userBubble.dataset.msgIndex = state.messages.length - 1;
  updateRetryVisibility();
  chatInput.value = "";
  autoGrow(chatInput);

  const pending = addBubble("other", "…", "pending");
  const sendBtn = chatForm.querySelector("button[type=submit]");
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system: state.system, messages: state.messages }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");

    pending.remove();
    const replyBubble = addBubble("other", data.reply);
    state.messages.push({ role: "assistant", content: data.reply });
    replyBubble.dataset.msgIndex = state.messages.length - 1;
    speak(data.reply);
  } catch (err) {
    pending.remove();
    addBubble("other", err.message, "error");
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

endBtn.addEventListener("click", async () => {
  if (state.messages.length === 0) {
    alert("Say at least one line first.");
    return;
  }
  endBtn.disabled = true;
  endBtn.textContent = "Getting feedback…";
  feedbackPanel.hidden = false;
  feedbackPanel.textContent = "Thinking through how that went…";

  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedbackSystem: state.feedbackSystem, messages: state.messages }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to get feedback.");
    feedbackPanel.textContent = data.feedback;
    if (state.scenarioId) appendSession(state.scenarioId, data.feedback);
  } catch (err) {
    feedbackPanel.textContent = `Couldn't get feedback: ${err.message}`;
  } finally {
    endBtn.disabled = false;
    endBtn.textContent = "End conversation & get feedback";
    feedbackPanel.scrollIntoView({ behavior: "smooth", block: "end" });
  }
});

newScenarioBtn.addEventListener("click", () => {
  if (state.messages.length > 0 && !confirm("Start a new scenario? This conversation won't be saved.")) return;
  resetToSetup();
});
