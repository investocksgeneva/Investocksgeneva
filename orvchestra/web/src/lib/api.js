// Thin fetch wrapper. Every request is same-origin: the built app is served
// by the same FastAPI process that serves /api, /track, and /art, so there
// is no configured base URL and nothing CORS-related to think about.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function post(path, body) {
  return request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

function del(path) {
  return request(path, { method: "DELETE" });
}

export const api = {
  home: () => request("/api/home"),
  search: (q) => request(`/api/search?q=${encodeURIComponent(q)}`),

  artists: () => request("/api/artists"),
  artist: (id) => request(`/api/artists/${encodeURIComponent(id)}`),
  albums: () => request("/api/albums"),
  album: (id) => request(`/api/albums/${encodeURIComponent(id)}`),
  genres: () => request("/api/genres"),
  genre: (id) => request(`/api/genres/${encodeURIComponent(id)}`),
  years: () => request("/api/years"),
  year: (year) => request(`/api/years/${encodeURIComponent(year)}`),

  playlists: () => request("/api/playlists"),
  playlist: (id) => request(`/api/playlists/${encodeURIComponent(id)}`),
  createSmartPlaylist: (name, description, rules) => post("/api/playlists", { name, description, rules }),
  deletePlaylist: (id) => del(`/api/playlists/${encodeURIComponent(id)}`),

  statsSummary: (period) => request(`/api/stats/summary?period=${encodeURIComponent(period)}`),
  statsTop: (kind, period, limit = 20) =>
    request(`/api/stats/top?kind=${kind}&period=${encodeURIComponent(period)}&limit=${limit}`),
  statsEncore: (months = 12) => request(`/api/stats/encore?months=${months}`),
  statsWrapped: (year) => request(`/api/stats/wrapped/${encodeURIComponent(year)}`),

  setRating: (trackId, rating) => post(`/api/tracks/${encodeURIComponent(trackId)}/rating`, { rating }),

  outputs: () => request("/api/outputs"),
  refreshOutputs: () => post("/api/outputs/refresh"),
  selectOutput: (id) => post(`/api/outputs/${encodeURIComponent(id)}/select`),

  nowPlaying: () => request("/api/now-playing"),
  queue: () => request("/api/queue"),
  playQueue: (trackIds, startIndex = 0) => post("/api/queue/play", { track_ids: trackIds, start_index: startIndex }),

  resume: () => post("/api/playback/resume"),
  pause: () => post("/api/playback/pause"),
  stop: () => post("/api/playback/stop"),
  next: () => post("/api/playback/next"),
  previous: () => post("/api/playback/previous"),
  seek: (positionSeconds) => post("/api/playback/seek", { position_seconds: positionSeconds }),
  setVolume: (level) => post("/api/playback/volume", { level }),
  browserState: (playing) => post("/api/playback/browser-state", { playing }),
  reportProgress: (positionSeconds) => post("/api/playback/progress", { position_seconds: positionSeconds }),
};

const STREAM_EXTENSION_BY_CODEC = { FLAC: "flac", MP3: "mp3", WAV: "wav", AAC: "m4a", ALAC: "m4a" };

export function trackStreamUrl(track) {
  const ext = STREAM_EXTENSION_BY_CODEC[track.codec] || "bin";
  return `/track/${track.id}.${ext}`;
}

export function formatDuration(totalSeconds) {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "--:--";
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function hiResBadge(track) {
  if (!track) return null;
  const parts = [track.codec];
  if (track.bit_depth && track.sample_rate) {
    parts.push(`${track.bit_depth}/${Math.round(track.sample_rate / 1000)}`);
  } else if (track.sample_rate) {
    parts.push(`${Math.round(track.sample_rate / 1000)}kHz`);
  }
  return parts.filter(Boolean).join(" ");
}
