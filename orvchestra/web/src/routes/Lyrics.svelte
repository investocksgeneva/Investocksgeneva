<script>
  import { api } from "../lib/api.js";
  import { player } from "../lib/player.svelte.js";

  // Matches a line like "[02:31.45]some lyric text" -- the informal .lrc
  // convention. Anything not matching this on at least one line is treated
  // as plain, unsynced lyrics instead.
  const TIME_RE = /^\[(\d+):(\d+(?:\.\d+)?)\](.*)$/;

  let rawLyrics = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let lineEls = $state([]);
  let lastTrackId = null;

  function parseLrc(text) {
    const parsed = [];
    for (const line of text.split(/\r?\n/)) {
      const m = TIME_RE.exec(line.trim());
      if (m) {
        parsed.push({ time: Number(m[1]) * 60 + Number(m[2]), text: m[3].trim() });
      }
    }
    return parsed;
  }

  const synced = $derived(rawLyrics ? parseLrc(rawLyrics) : []);
  const isSynced = $derived(synced.length > 0);
  const plainLines = $derived(rawLyrics ? rawLyrics.split(/\r?\n/) : []);

  const currentIndex = $derived.by(() => {
    if (!isSynced) return -1;
    const pos = player.positionSeconds;
    let idx = -1;
    for (const [i, line] of synced.entries()) {
      if (line.time <= pos) idx = i;
      else break;
    }
    return idx;
  });

  async function loadLyrics(trackId) {
    loading = true;
    error = null;
    rawLyrics = null;
    try {
      const res = await api.lyrics(trackId);
      rawLyrics = res.lyrics;
    } catch (err) {
      error = String(err.message || err);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const trackId = player.currentTrack?.id ?? null;
    if (trackId !== lastTrackId) {
      lastTrackId = trackId;
      if (trackId) loadLyrics(trackId);
      else rawLyrics = null;
    }
  });

  $effect(() => {
    const idx = currentIndex;
    if (idx >= 0 && lineEls[idx]) {
      lineEls[idx].scrollIntoView({ block: "center", behavior: "smooth" });
    }
  });
</script>

<h1>Lyrics</h1>

{#if !player.currentTrack}
  <p class="empty-state">Nothing playing. Pick an album, artist, or search result.</p>
{:else}
  <div class="track-title" style="text-align:left;">{player.currentTrack.title}</div>
  <div class="track-artist" style="text-align:left; margin-bottom:20px;">
    {player.currentTrack.artist ?? player.currentTrack.album_artist ?? ""}
  </div>

  {#if loading}
    <p class="empty-state">Loading…</p>
  {:else if error}
    <p class="empty-state">Couldn't load lyrics: {error}</p>
  {:else if !rawLyrics}
    <p class="empty-state">
      No lyrics found for this track. Add an embedded "LYRICS" tag, or drop a matching
      .lrc (time-synced) or .txt (plain) file next to it in your library folder, then rescan.
    </p>
  {:else if isSynced}
    <div class="lyrics-lines">
      {#each synced as line, i (i)}
        <p bind:this={lineEls[i]} class="lyrics-line" class:active={i === currentIndex}>
          {line.text || " "}
        </p>
      {/each}
    </div>
  {:else}
    <div class="lyrics-lines">
      {#each plainLines as line, i (i)}
        <p class="lyrics-line">{line || " "}</p>
      {/each}
    </div>
  {/if}
{/if}
