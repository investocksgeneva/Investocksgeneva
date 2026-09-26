<script>
  import { player } from "./player.svelte.js";
  import { togglePlayPause } from "./player.svelte.js";
  import { navigate } from "./router.svelte.js";

  const artUrl = $derived(player.currentTrack?.art_url_small ?? null);
</script>

{#if player.currentTrack}
  <div class="miniplayer">
    <button class="open-now-playing" onclick={() => navigate("/now-playing")} aria-label="Open Now Playing">
      {#if artUrl}
        <img src={artUrl} alt="" />
      {:else}
        <div class="art-placeholder"></div>
      {/if}
      <div class="info">
        <div class="title">{player.currentTrack.title}</div>
        <div class="subtitle">{player.currentTrack.artist ?? player.currentTrack.album_artist ?? ""}</div>
      </div>
    </button>
    <button class="icon-button" aria-label={player.isPlaying ? "Pause" : "Play"} onclick={togglePlayPause}>
      {player.isPlaying ? "⏸" : "▶"}
    </button>
  </div>
{/if}
