// Central playback state. There are two entirely different playback
// mechanisms behind one shared shape:
//
//  - a DLNA renderer (the WiiM): Orvchestra's backend is the one actually
//    driving playback (AVTransport/RenderingControl), so state comes from
//    polling GET /api/now-playing.
//  - "this device": nothing on the backend plays anything -- the browser's
//    own <audio> element does, pointed straight at /track/{id}.{ext}. The
//    backend still owns the *queue* (so Queue/Now Playing look the same
//    regardless of output), but position/duration/play-state for this mode
//    come from the audio element itself, not from polling.
//
// Every control function below calls the matching API endpoint and applies
// whatever `now_playing`-shaped result comes back through `applyNowPlaying`,
// which is where the this-device/renderer branch happens.

import { api, trackStreamUrl } from "./api.js";

const THIS_DEVICE = "this-device";
const RENDERER_POLL_INTERVAL_MS = 1000;

export const player = $state({
  outputs: [],
  selectedOutput: THIS_DEVICE,
  currentTrack: null,
  queueTracks: [],
  queuePosition: 0,
  isPlaying: false,
  positionSeconds: 0,
  durationSeconds: null,
  volume: 1,
  loading: false,
  error: null,
});

let audioEl = null;
let pollTimer = null;
let lastReportedProgressAt = 0;

// Throttled so a this-device play gets recorded via the same threshold
// logic a WiiM play does (see PlaybackService.report_browser_position)
// without hammering the backend on every timeupdate tick (which fires
// several times a second).
const PROGRESS_REPORT_INTERVAL_MS = 5000;

export function bindAudioElement(el) {
  audioEl = el;
  audioEl.addEventListener("play", () => {
    if (player.selectedOutput !== THIS_DEVICE) return;
    player.isPlaying = true;
    api.browserState(true).catch(() => {});
  });
  audioEl.addEventListener("pause", () => {
    if (player.selectedOutput !== THIS_DEVICE) return;
    player.isPlaying = false;
    api.browserState(false).catch(() => {});
  });
  audioEl.addEventListener("timeupdate", () => {
    if (player.selectedOutput !== THIS_DEVICE) return;
    player.positionSeconds = audioEl.currentTime;
    const now = Date.now();
    if (now - lastReportedProgressAt >= PROGRESS_REPORT_INTERVAL_MS) {
      lastReportedProgressAt = now;
      api.reportProgress(audioEl.currentTime).catch(() => {});
    }
  });
  audioEl.addEventListener("durationchange", () => {
    if (player.selectedOutput === THIS_DEVICE && Number.isFinite(audioEl.duration)) {
      player.durationSeconds = audioEl.duration;
    }
  });
  audioEl.addEventListener("ended", async () => {
    // The track finished, which is itself worth reporting as final
    // progress (a short track's periodic 5s reports might otherwise never
    // land squarely on/past its own threshold).
    await api.reportProgress(audioEl.duration || audioEl.currentTime).catch(() => {});
    await api.browserState(false).catch(() => {});
    await next();
  });
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      applyNowPlaying(await api.nowPlaying());
    } catch {
      // A transient poll failure (renderer briefly unreachable) isn't worth
      // surfacing as an error; the next tick will likely succeed.
    }
  }, RENDERER_POLL_INTERVAL_MS);
}

async function applyNowPlaying(np) {
  player.queuePosition = np.queue_position ?? player.queuePosition;
  player.currentTrack = np.track ?? null;

  if (player.selectedOutput === THIS_DEVICE) {
    if (audioEl && np.track) {
      const url = trackStreamUrl(np.track);
      if (!audioEl.src.endsWith(url)) {
        audioEl.src = url;
        lastReportedProgressAt = 0; // report promptly on the new track, don't wait out the old throttle window
        try {
          await audioEl.play();
        } catch {
          // Autoplay may be blocked until the user interacts with the page;
          // they can just press play themselves.
        }
      }
    } else if (audioEl) {
      audioEl.pause();
      audioEl.removeAttribute("src");
    }
    return;
  }

  if ("transport_state" in np) player.isPlaying = np.transport_state === "PLAYING";
  if ("position_seconds" in np) player.positionSeconds = np.position_seconds ?? 0;
  if ("duration_seconds" in np) player.durationSeconds = np.duration_seconds;
  if ("volume" in np && np.volume != null) player.volume = np.volume;
}

async function refreshQueueList() {
  const { tracks, position } = await api.queue();
  player.queueTracks = tracks;
  player.queuePosition = position;
}

export async function initPlayer() {
  player.outputs = await api.outputs();
  const selected = player.outputs.find((o) => o.selected);
  if (selected) player.selectedOutput = selected.id;

  await refreshQueueList().catch(() => {});
  try {
    await applyNowPlaying(await api.nowPlaying());
  } catch {
    // Nothing queued yet -- fine, nothing to restore.
  }
  if (player.selectedOutput !== THIS_DEVICE) startPolling();
}

export async function refreshOutputs() {
  player.outputs = await api.refreshOutputs();
}

export async function selectOutput(id) {
  await api.selectOutput(id);
  player.selectedOutput = id;
  stopPolling();
  if (id !== THIS_DEVICE) {
    startPolling();
  } else if (audioEl) {
    audioEl.pause();
    audioEl.removeAttribute("src");
  }
}

export async function playQueue(trackIds, startIndex = 0) {
  player.loading = true;
  player.error = null;
  try {
    const np = await api.playQueue(trackIds, startIndex);
    await refreshQueueList();
    await applyNowPlaying(np);
    if (player.selectedOutput !== THIS_DEVICE) startPolling();
  } catch (err) {
    player.error = String(err.message || err);
  } finally {
    player.loading = false;
  }
}

export async function playRadioStation(station) {
  player.loading = true;
  player.error = null;
  try {
    const np = await api.radioPlay(station);
    player.queueTracks = [];
    await applyNowPlaying(np);
    if (player.selectedOutput !== THIS_DEVICE) startPolling();
  } catch (err) {
    player.error = String(err.message || err);
  } finally {
    player.loading = false;
  }
}

export async function togglePlayPause() {
  if (player.selectedOutput === THIS_DEVICE) {
    if (!audioEl) return;
    if (audioEl.paused) await audioEl.play();
    else audioEl.pause();
    return;
  }
  const np = player.isPlaying ? await api.pause() : await api.resume();
  await applyNowPlaying(np);
}

export async function next() {
  await applyNowPlaying(await api.next());
}

export async function previous() {
  await applyNowPlaying(await api.previous());
}

export async function seek(seconds) {
  if (player.selectedOutput === THIS_DEVICE) {
    if (audioEl) audioEl.currentTime = seconds;
    player.positionSeconds = seconds;
    return;
  }
  await applyNowPlaying(await api.seek(seconds));
}

export async function setVolume(level) {
  if (player.selectedOutput === THIS_DEVICE) {
    if (audioEl) audioEl.volume = level;
    player.volume = level;
    return;
  }
  await applyNowPlaying(await api.setVolume(level));
}

export { THIS_DEVICE };
