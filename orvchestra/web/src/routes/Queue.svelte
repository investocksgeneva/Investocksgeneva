<script>
  import { player, playQueue } from "../lib/player.svelte.js";
</script>

<h1>Queue</h1>

{#if player.queueTracks.length === 0}
  <p class="empty-state">Nothing queued. Play an album, artist, or search result to get started.</p>
{:else}
  <div class="row-list">
    {#each player.queueTracks as track, index (`${track.id}-${index}`)}
      <button
        class="row-item"
        class:active={index === player.queuePosition}
        onclick={() =>
          playQueue(
            player.queueTracks.map((t) => t.id),
            index,
          )}
      >
        <span class="row-index">{index + 1}</span>
        <div class="row-text">
          <div class="row-title">{track.title}</div>
          <div class="row-subtitle">{track.artist ?? track.album_artist ?? ""} — {track.album ?? ""}</div>
        </div>
      </button>
    {/each}
  </div>
{/if}
