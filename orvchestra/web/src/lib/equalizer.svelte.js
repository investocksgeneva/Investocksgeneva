// Client-side graphic equalizer for "This device" playback, built on the Web
// Audio API. It only ever touches the browser's own <audio> element -- a
// DLNA renderer (the WiiM) receives the raw file straight from the engine,
// bypassing the browser entirely, so this has no effect on that output.

const STORAGE_KEY = "orvchestra.eq.v1";

export const EQ_BANDS = [
  { freq: 60, label: "60Hz" },
  { freq: 150, label: "150Hz" },
  { freq: 400, label: "400Hz" },
  { freq: 1000, label: "1kHz" },
  { freq: 2400, label: "2.4kHz" },
  { freq: 6000, label: "6kHz" },
  { freq: 15000, label: "15kHz" },
];

export const EQ_PRESETS = {
  Flat: [0, 0, 0, 0, 0, 0, 0],
  "Bass Boost": [6, 4, 2, 0, 0, 0, 0],
  Vocal: [-2, -1, 2, 4, 3, 1, 0],
  Treble: [0, 0, 0, 0, 2, 4, 6],
  Loudness: [5, 3, -1, -3, -1, 3, 5],
  Rock: [4, 2, -1, -2, 1, 3, 4],
};

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed.gains) && parsed.gains.length === EQ_BANDS.length) return parsed;
  } catch {
    // Corrupt/unavailable storage just falls back to defaults.
  }
  return null;
}

const stored = loadStored();

export const eq = $state({
  enabled: stored?.enabled ?? false,
  gains: stored?.gains ?? EQ_BANDS.map(() => 0),
});

let audioCtx = null;
let filters = [];

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ enabled: eq.enabled, gains: eq.gains }));
  } catch {
    // Private browsing / storage full -- the EQ still works for this session.
  }
}

function applyGains() {
  filters.forEach((filter, i) => {
    filter.gain.value = eq.enabled ? eq.gains[i] : 0;
  });
}

// Lazily built on the audio element's first "play". Building an AudioContext
// before a user gesture leaves it permanently suspended on iOS Safari, and
// `createMediaElementSource` can only ever be called once per <audio>
// element, so this must be idempotent and called no earlier than first play.
export function ensureGraph(audioEl) {
  if (audioCtx) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return; // Web Audio unsupported -- EQ has no effect, playback itself is unaffected.

  audioCtx = new Ctx();
  const sourceNode = audioCtx.createMediaElementSource(audioEl);
  filters = EQ_BANDS.map((band, i) => {
    const filter = audioCtx.createBiquadFilter();
    filter.type = "peaking";
    filter.frequency.value = band.freq;
    filter.Q.value = 1.1;
    filter.gain.value = eq.enabled ? eq.gains[i] : 0;
    return filter;
  });

  sourceNode.connect(filters[0]);
  for (let i = 0; i < filters.length - 1; i++) filters[i].connect(filters[i + 1]);
  filters[filters.length - 1].connect(audioCtx.destination);
}

export function resumeContext() {
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
}

export function setEnabled(value) {
  eq.enabled = value;
  applyGains();
  persist();
}

export function setBandGain(index, value) {
  eq.gains[index] = value;
  applyGains();
  persist();
}

export function applyPreset(name) {
  const preset = EQ_PRESETS[name];
  if (!preset) return;
  eq.gains = [...preset];
  eq.enabled = true;
  applyGains();
  persist();
}

export function resetEq() {
  eq.gains = EQ_BANDS.map(() => 0);
  applyGains();
  persist();
}
