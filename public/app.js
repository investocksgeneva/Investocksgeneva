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

let state = {
  system: "",
  feedbackSystem: "",
  messages: [], // {role: 'user'|'assistant', content: string}
};

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
  state = { system: "", feedbackSystem: "", messages: [] };
  messagesEl.innerHTML = "";
  feedbackPanel.hidden = true;
  feedbackPanel.textContent = "";
  setupScreen.hidden = false;
  chatScreen.hidden = true;
  newScenarioBtn.hidden = true;
  setupForm.reset();
}

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

    setupScreen.hidden = true;
    chatScreen.hidden = false;
    newScenarioBtn.hidden = false;
    messagesEl.innerHTML = "";
    feedbackPanel.hidden = true;

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

  addBubble("user", text);
  state.messages.push({ role: "user", content: text });
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
    addBubble("other", data.reply);
    state.messages.push({ role: "assistant", content: data.reply });
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
