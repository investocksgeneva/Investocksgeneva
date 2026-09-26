// Central playback state. There are two entirely different playback
// mechanisms behind one shared shape:
//
//  - a DLNA renderer (the WiiM): Orvchestra's backend is the one actually
//    driving playback (AVTransport/RenderingControl), so state comes from
//    polling GET /api/now-playing.
//  - "this device": nothing on the backend plays anything -- the browser's
//    own <audio> element does, pointed straight at /track/{id}.{ext} for a
//    local file or a radio station's stream URL. The backend still owns the
//    *queue* (so Queue/Now Playing look the same regardless of output), but
//    position/duration/play-state for this mode come from the audio element
//    itself, not from polling.
//
// This-device playback actually uses *two* separate <audio> elements, not
// one: the regular one gets wired into a Web Audio graph (equalizer.svelte.js)
// for the EQ/visualizer, and once an element has ever been connected to Web
// Audio, any cross-origin content it plays afterward without CORS headers is
// permanently silenced by the browser (a security measure, not a bug) --
// almost no internet radio station sends those headers. A second, plain
// element that's never touched by Web Audio sidesteps that entirely, at the
// cost of the EQ/visualizer simply not applying to radio.
//
// Every control function below calls the matching API endpoint and applies
// whatever `now_playing`-shaped result comes back through `applyNowPlaying`,
// which is where the this-device/renderer branch happens.

import { api, trackStreamUrl } from "./api.js";
import { loadStream, stopStream } from "./streamSource.js";

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
let radioAudioEl = null;
let pollTimer = null;
let lastReportedProgressAt = 0;
// hls.js rewrites an element's .src to an internal blob: URL once attached,
// so the "is this already loaded" check has to compare against the URL we
// asked for, not whatever the element's own .src happens to read afterward.
// Tracked separately per element since either can have something loaded.
let localLoadedUrl = null;
let radioLoadedUrl = null;

// Throttled so a this-device play gets recorded via the same threshold
// logic a WiiM play does (see PlaybackService.report_browser_position)
// without hammering the backend on every timeupdate tick (which fires
// several times a second).
const PROGRESS_REPORT_INTERVAL_MS = 5000;

function activeEl() {
  return player.currentTrack?.is_radio ? radioAudioEl : audioEl;
}

function wireTransportEvents(el, isRadio) {
  // Both elements sit bound at all times, but only one is ever "the" active
  // source at once -- a stray event from the currently-inactive one (e.g.
  // leftover buffering after a switch) must not clobber shared state.
  const isActive = () => player.selectedOutput === THIS_DEVICE && Boolean(player.currentTrack?.is_radio) === isRadio;

  el.addEventListener("play", () => {
    if (!isActive()) return;
    player.isPlaying = true;
    api.browserState(true).catch(() => {});
  });
  el.addEventListener("pause", () => {
    if (!isActive()) return;
    player.isPlaying = false;
    api.browserState(false).catch(() => {});
  });

  if (isRadio) {
    // A live stream ending/erroring isn't "track finished" in any meaningful
    // sense -- there's no queue to advance, just note playback stopped.
    el.addEventListener("ended", () => {
      if (!isActive()) return;
      player.isPlaying = false;
      api.browserState(false).catch(() => {});
    });
    return;
  }

  el.addEventListener("timeupdate", () => {
    if (!isActive()) return;
    player.positionSeconds = el.currentTime;
    const now = Date.now();
    if (now - lastReportedProgressAt >= PROGRESS_REPORT_INTERVAL_MS) {
      lastReportedProgressAt = now;
      api.reportProgress(el.currentTime).catch(() => {});
    }
  });
  el.addEventListener("durationchange", () => {
    if (isActive() && Number.isFinite(el.duration)) {
      player.durationSeconds = el.duration;
    }
  });
  el.addEventListener("ended", async () => {
    // The track finished, which is itself worth reporting as final progress
    // (a short track's periodic 5s reports might otherwise never land
    // squarely on/past its own threshold).
    if (!isActive()) return;
    await api.reportProgress(el.duration || el.currentTime).catch(() => {});
    await api.browserState(false).catch(() => {});
    await next();
  });
}

export function bindAudioElement(el) {
  audioEl = el;
  wireTransportEvents(el, false);
}

export function bindRadioAudioElement(el) {
  radioAudioEl = el;
  wireTransportEvents(el, true);
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

function stopBoth() {
  if (audioEl) {
    localLoadedUrl = null;
    stopStream(audioEl);
  }
  if (radioAudioEl) {
    radioLoadedUrl = null;
    stopStream(radioAudioEl);
  }
}

async function applyNowPlaying(np) {
  player.queuePosition = np.queue_position ?? player.queuePosition;
  player.currentTrack = np.track ?? null;

  if (player.selectedOutput === THIS_DEVICE) {
    if (!np.track) {
      stopBoth();
      return;
    }

    const isRadio = Boolean(np.track.is_radio);
    // Only one of the two elements should ever be audible at once -- silence
    // whichever one isn't relevant to what's playing now.
    if (isRadio && audioEl && localLoadedUrl) {
      localLoadedUrl = null;
      stopStream(audioEl);
    }
    if (!isRadio && radioAudioEl && radioLoadedUrl) {
      radioLoadedUrl = null;
      stopStream(radioAudioEl);
    }

    const el = isRadio ? radioAudioEl : audioEl;
    if (el) {
      const url = trackStreamUrl(np.track);
      const alreadyLoaded = (isRadio ? radioLoadedUrl : localLoadedUrl) === url;
      if (!alreadyLoaded) {
        if (isRadio) radioLoadedUrl = url;
        else localLoadedUrl = url;
        await loadStream(el, url);
        lastReportedProgressAt = 0; // report promptly on the new track, don't wait out the old throttle window
        try {
          await el.play();
        } catch {
          // Autoplay may be blocked until the user interacts with the page;
          // they can just press play themselves.
        }
      }
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
  } else {
    stopBoth();
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
    const el = activeEl();
    if (!el) return;
    if (el.paused) await el.play();
    else el.pause();
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
    const el = activeEl();
    if (el) el.currentTime = seconds;
    player.positionSeconds = seconds;
    return;
  }
  await applyNowPlaying(await api.seek(seconds));
}

export async function setVolume(level) {
  if (player.selectedOutput === THIS_DEVICE) {
    const el = activeEl();
    if (el) el.volume = level;
    player.volume = level;
    return;
  }
  await applyNowPlaying(await api.setVolume(level));
}

export { THIS_DEVICE };
