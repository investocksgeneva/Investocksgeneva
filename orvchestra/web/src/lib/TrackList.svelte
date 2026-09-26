<script>
  import { player, playQueue } from "./player.svelte.js";

  let { tracks, showArt = false, showAlbum = false } = $props();

  function play(index) {
    playQueue(
      tracks.map((t) => t.id),
      index,
    );
  }
</script>

<div class="row-list">
  {#each tracks as track, index (track.id)}
    <button class="row-item" class:active={player.currentTrack?.id === track.id} onclick={() => play(index)}>
      {#if showArt}
        {#if track.art_url_small}
          <img class="row-art" src={track.art_url_small} alt="" loading="lazy" />
        {:else}
          <div class="row-art art-placeholder"></div>
        {/if}
      {:else}
        <span class="row-index">{track.track_number ?? index + 1}</span>
      {/if}
      <div class="row-text">
        <div class="row-title">{track.title}</div>
        <div class="row-subtitle">
          {track.artist ?? track.album_artist ?? ""}{showAlbum && track.album ? ` — ${track.album}` : ""}
        </div>
      </div>
      {#if !track.online}
        <span class="badge" style="background: var(--danger)">Offline</span>
      {/if}
    </button>
  {/each}
</div>
