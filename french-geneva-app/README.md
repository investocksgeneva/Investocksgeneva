# Français — Genève

A mobile-first French learning app built around daily life in Geneva. It's an
installable Progressive Web App (works on iOS/Android from the browser via
"Add to Home Screen"), starting with **Week 1: Foundations** — greetings,
courtesy, and Swiss-specific numbers (septante, huitante, nonante).

## Features

- **Session-by-session lessons**: core phrases, grammar notes, mini-dialogues,
  and drills, each with tap-to-listen French pronunciation (Web Speech API).
- **Swiss numbers callouts**: flags the France-vs-Switzerland number trap
  (70/80/90) that most France-focused apps miss.
- **Role-play checkpoint**: an end-of-week unscripted transaction checklist.
- **Vocabulary flashcards**: ~20-word bank with flip-to-reveal and
  known/practice tracking.
- **Progress tracking**: persisted locally (no account/server needed).

## Development

```bash
npm install
npm run dev       # start dev server
npm run build     # type-check + production build
npm run preview   # preview the production build
```

## Tech

React + TypeScript + Vite, `vite-plugin-pwa` for installability, and the
browser's built-in `speechSynthesis` API (`fr-FR`) for pronunciation — no
backend required.
