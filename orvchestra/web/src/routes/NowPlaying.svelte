<script>
  import { onMount } from "svelte";
  import {
    player,
    togglePlayPause,
    next,
    previous,
    seek,
    setVolume,
    selectOutput,
    refreshOutputs,
  } from "../lib/player.svelte.js";
  import { api, formatDuration, hiResBadge } from "../lib/api.js";
  import { navigate } from "../lib/router.svelte.js";
  import { resumeContext } from "../lib/equalizer.svelte.js";
  import Visualizer from "../lib/Visualizer.svelte";

  let seeking = $state(false);
  let seekValue = $state(0);

  async function rate(value) {
    const track = player.currentTrack;
    if (!track) return;
    // A tap on the currently-set star clears the rating rather than
    // re-setting the same value, so there's a way to un-rate a track.
    const newRating = track.rating === value ? null : value;
    await api.setRating(track.id, newRating);
    track.rating = newRating;
  }

  onMount(() => {
    refreshOutputs();
  });

  function onSeekInput(event) {
    seeking = true;
    seekValue = Number(event.target.value);
  }

  function onSeekCommit(event) {
    seek(Number(event.target.value));
    seeking = false;
  }

  const displayPosition = $derived(seeking ? seekValue : player.positionSeconds);
  const knownDuration = $derived(player.durationSeconds ?? player.currentTrack?.duration_seconds ?? 0);
</script>

<div class="now-playing">
  {#if !player.currentTrack}
    <p class="empty-state">Nothing playing. Pick an album, artist, or search result.</p>
  {:else}
    {#if player.currentTrack.art_url_large}
      <img class="big-art" src={player.currentTrack.art_url_large} alt="" />
    {:else}
      <div class="big-art"></div>
    {/if}
    <div class="track-title">{player.currentTrack.title}</div>
    <div class="track-artist">{player.currentTrack.artist ?? player.currentTrack.album_artist ?? ""}</div>
    {#if hiResBadge(player.currentTrack)}
      <span class="badge">{hiResBadge(player.currentTrack)}</span>
    {/if}

    <div class="star-rating">
      {#each [1, 2, 3, 4, 5] as value (value)}
        <button aria-label={`Rate ${value} star${value === 1 ? "" : "s"}`} onclick={() => rate(value)}>
          {(player.currentTrack.rating ?? 0) >= value ? "★" : "☆"}
        </button>
      {/each}
    </div>

    <Visualizer />

    <input
      class="seek-bar"
      type="range"
      min="0"
      max={knownDuration || 1}
      value={displayPosition}
      oninput={onSeekInput}
      onchange={onSeekCommit}
    />
    <div class="time-row">
      <span>{formatDuration(displayPosition)}</span>
      <span>{formatDuration(knownDuration)}</span>
    </div>

    <div class="transport-controls">
      <button onclick={previous} aria-label="Previous track">⏮</button>
      <button
        class="play-button"
        onclick={() => { resumeContext(); togglePlayPause(); }}
        aria-label={player.isPlaying ? "Pause" : "Play"}
      >
        {player.isPlaying ? "⏸" : "▶"}
      </button>
      <button onclick={next} aria-label="Next track">⏭</button>
    </div>

    <div class="volume-row">
      <span>🔈</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={player.volume}
        oninput={(event) => setVolume(Number(event.target.value))}
      />
    </div>

    <button class="link-button" onclick={() => navigate("/lyrics")}>📜 Lyrics</button>
    <button class="link-button" onclick={() => navigate("/equalizer")}>🎚️ Equalizer</button>
  {/if}

  <div class="output-picker">
    <div class="section-title">Play on</div>
    {#each player.outputs as output (output.id)}
      <button
        class="output-option"
        class:selected={output.id === player.selectedOutput}
        onclick={() => selectOutput(output.id)}
      >
        <span>{output.kind === "browser" ? "📱 " : "🔊 "}{output.name}</span>
        {#if output.id === player.selectedOutput}<span>✓</span>{/if}
      </button>
    {/each}
    <button class="link-button" onclick={refreshOutputs}>Refresh devices</button>
  </div>
</div>
