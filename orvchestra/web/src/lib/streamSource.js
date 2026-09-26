// Points the shared <audio> element at a stream URL, transparently handling
// HLS (.m3u8) sources -- common for internet radio (BBC's network stations,
// among others, serve exclusively over HLS now). Only Safari's <audio>
// understands HLS natively (via AVFoundation); everywhere else needs hls.js
// to demux segments into a MediaSource buffer the element can actually play,
// or it silently "plays" with no audio at all.

// Loaded lazily (not a top-level import) so its ~200KB doesn't bloat the
// initial bundle for the common case -- playing a local file -- which never
// touches this at all.
let hlsModulePromise = null;
function loadHlsModule() {
  hlsModulePromise ??= import("hls.js").then((mod) => mod.default);
  return hlsModulePromise;
}

let hls = null;

function isHlsUrl(url) {
  return /\.m3u8(\?|$)/i.test(url);
}

function hasNativeHlsSupport(audioEl) {
  return audioEl.canPlayType("application/vnd.apple.mpegurl") !== "";
}

export async function loadStream(audioEl, url) {
  if (hls) {
    hls.destroy();
    hls = null;
  }
  if (isHlsUrl(url) && !hasNativeHlsSupport(audioEl)) {
    const Hls = await loadHlsModule();
    if (Hls.isSupported()) {
      hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(audioEl);
      return;
    }
  }
  audioEl.src = url;
}

export function stopStream(audioEl) {
  if (hls) {
    hls.destroy();
    hls = null;
  }
  audioEl.pause();
  audioEl.removeAttribute("src");
}
