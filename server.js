import "dotenv/config";
import express from "express";
import Anthropic from "@anthropic-ai/sdk";
import { buildRoleplaySystemPrompt, buildFeedbackPrompt } from "./server/prompts.js";

const app = express();
const PORT = process.env.PORT || 3000;
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5";

app.use(express.json({ limit: "1mb" }));
app.use(express.static("public"));

function getClient() {
  if (!process.env.ANTHROPIC_API_KEY) return null;
  return new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
}

function isValidMessages(messages) {
  return (
    Array.isArray(messages) &&
    messages.length > 0 &&
    messages.every(
      (m) =>
        m &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string" &&
        m.content.length > 0
    )
  );
}

app.post("/api/system", (req, res) => {
  const { situation, otherPerson, yourGoal, difficulty } = req.body || {};
  if (!situation || !otherPerson) {
    return res.status(400).json({ error: "situation and otherPerson are required." });
  }
  const scenario = { situation, otherPerson, yourGoal, difficulty };
  res.json({
    system: buildRoleplaySystemPrompt(scenario),
    feedbackSystem: buildFeedbackPrompt(scenario),
  });
});

app.post("/api/chat", async (req, res) => {
  const client = getClient();
  if (!client) {
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on the server. Add it to .env and restart." });
  }
  const { system, messages } = req.body || {};
  if (typeof system !== "string" || !system) {
    return res.status(400).json({ error: "system prompt is required." });
  }
  if (!isValidMessages(messages)) {
    return res.status(400).json({ error: "messages must be a non-empty array of {role, content}." });
  }

  try {
    const response = await client.messages.create({
      model: MODEL,
      max_tokens: 400,
      system,
      messages,
    });
    const reply = response.content.find((b) => b.type === "text")?.text ?? "";
    res.json({ reply });
  } catch (err) {
    console.error(err);
    res.status(502).json({ error: "Claude API request failed. Check server logs." });
  }
});

app.post("/api/feedback", async (req, res) => {
  const client = getClient();
  if (!client) {
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on the server. Add it to .env and restart." });
  }
  const { feedbackSystem, messages } = req.body || {};
  if (typeof feedbackSystem !== "string" || !feedbackSystem) {
    return res.status(400).json({ error: "feedbackSystem is required." });
  }
  if (!isValidMessages(messages)) {
    return res.status(400).json({ error: "messages must be a non-empty array of {role, content}." });
  }

  try {
    const transcript = messages
      .map((m) => `${m.role === "user" ? "USER" : "OTHER PERSON"}: ${m.content}`)
      .join("\n\n");
    const response = await client.messages.create({
      model: MODEL,
      max_tokens: 700,
      system: feedbackSystem,
      messages: [{ role: "user", content: `TRANSCRIPT\n\n${transcript}` }],
    });
    const feedback = response.content.find((b) => b.type === "text")?.text ?? "";
    res.json({ feedback });
  } catch (err) {
    console.error(err);
    res.status(502).json({ error: "Claude API request failed. Check server logs." });
  }
});

app.listen(PORT, () => {
  console.log(`Articulations running at http://localhost:${PORT}`);
});
