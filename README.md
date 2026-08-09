## Hi there 👋

<!--
**investocksgeneva/Investocksgeneva** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

Here are some ideas to get you started:

- 🔭 I’m currently working on ...
- 🌱 I’m currently learning ...
- 👯 I’m looking to collaborate on ...
- 🤔 I’m looking for help with ...
- 💬 Ask me about ...
- 📫 How to reach me: ...
- 😄 Pronouns: ...
- ⚡ Fun fact: ...
-->

## Articulations

A personal rehearsal tool: describe a tough conversation you need to have, and Claude plays the other person so you can practice it before it's real. When you're done, it steps out of character and gives you coaching feedback on how the conversation went.

Text roleplay (Phase 1) and voice (Phase 2) are both in. Session memory / scenario templates (Phase 3) aren't built yet.

### Run it locally

```bash
npm install
cp .env.example .env   # then paste your Anthropic API key into .env
npm start
```

Open `http://localhost:3000`.

On your phone, open that URL in the browser (use your machine's LAN IP instead of `localhost` if running on your computer, e.g. `http://192.168.1.x:3000`), then use "Add to Home Screen" — it opens like a standalone app.

### How it works

- Fill in the situation, who you're talking to, your goal, and (optionally) how resistant they should be.
- Claude roleplays that person in a normal back-and-forth chat.
- Tap **End conversation & get feedback** any time to get out-of-character coaching on what worked and what to try differently.
- **New scenario** clears the conversation and starts fresh. Nothing is saved between sessions — it's a stateless rehearsal tool.

### Voice

On browsers that support the Web Speech API (Chrome, Edge, Safari on recent iOS/macOS):

- Tap the 🎤 mic button to speak your line instead of typing — it transcribes and sends automatically when you stop talking.
- Tap 🔊 in the top bar to have the other person's replies read aloud (uses the browser's built-in text-to-speech, no extra API key needed). Off by default; your choice is remembered locally.

If your browser doesn't support speech recognition or synthesis, those buttons just don't show up — typing still works everywhere.

### Stack

Plain HTML/CSS/JS frontend, a small Express server that proxies chat requests to the Claude API (so your API key never reaches the browser). No accounts, no database, no build step.
