<script>
  import { api } from "../lib/api.js";
  import AlbumGrid from "../lib/AlbumGrid.svelte";

  let { id } = $props();

  let artist = $state(null);
  let error = $state(null);

  $effect(() => {
    artist = null;
    error = null;
    api.artist(id).then(
      (a) => (artist = a),
      (err) => (error = String(err.message || err)),
    );
  });
</script>

{#if error}
  <p class="empty-state">{error}</p>
{:else if !artist}
  <p class="empty-state">Loading…</p>
{:else}
  <h1>{artist.artist}</h1>
  <p style="color: var(--text-muted); margin: -6px 0 0">
    {artist.album_count} album{artist.album_count === 1 ? "" : "s"} · {artist.track_count} track{artist.track_count === 1 ? "" : "s"}
  </p>
  <div class="section-title">Albums</div>
  <AlbumGrid albums={artist.albums} />
{/if}
