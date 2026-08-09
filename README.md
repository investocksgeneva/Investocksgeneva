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

All three phases are in: text roleplay, voice, and scenario templates with session memory.

### Run it locally

```bash
npm install
cp .env.example .env   # then paste your Anthropic API key into .env
npm start
```

Open `http://localhost:3000`.

### Add it to your home screen

On your phone, open the app's URL in the browser — use your machine's LAN IP instead of `localhost` if you're running the server on your computer (e.g. `http://192.168.1.x:3000`); both devices need to be on the same network.

- **iPhone (Safari):** tap the Share icon → **Add to Home Screen**.
- **Android (Chrome):** tap the ⋮ menu → **Add to Home screen** (or **Install app**).

It launches full-screen with its own icon, no browser bar — like a real app.

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

### Scenario templates & session memory

- Give a scenario a name before starting (e.g. "Dishes with Sam") to save it for reuse. It shows up under **Saved scenarios** on the setup screen next time.
- Each time you get feedback on a saved scenario, that session is recorded. Loading the scenario again shows a reminder of what came up last time, so you can pick up where you left off.
- **↺ Retry last line** mid-conversation removes your last line and the reply that followed, and puts your line back in the input to try again.
- All of this lives in your browser's local storage — nothing is sent anywhere except the roleplay/feedback text itself, and nothing syncs across devices.

### Stack

Plain HTML/CSS/JS frontend, a small Express server that proxies chat requests to the Claude API (so your API key never reaches the browser). No accounts, no database, no build step.
