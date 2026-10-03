<script>
  import { api, formatDuration } from "../lib/api.js";
  import { navigate } from "../lib/router.svelte.js";
  import { playQueue } from "../lib/player.svelte.js";
  import TrackList from "../lib/TrackList.svelte";

  let { id } = $props();

  let album = $state(null);
  let error = $state(null);

  $effect(() => {
    album = null;
    error = null;
    api.album(id).then(
      (a) => (album = a),
      (err) => (error = String(err.message || err)),
    );
  });

  function playAll() {
    if (album?.tracks.length) playQueue(album.tracks.map((t) => t.id), 0);
  }
</script>

{#if error}
  <p class="empty-state">{error}</p>
{:else if !album}
  <p class="empty-state">Loading…</p>
{:else}
  <div class="album-page">
    <div class="album-hero-row">
      <div class="album-art-pane">
        {#if album.art_url_large}
          <img
            src={album.art_url_large}
            alt=""
            class="album-art-img"
          />
        {/if}
        <h1 style="margin-top:16px; margin-bottom:2px">{album.album}</h1>
        {#if album.artist_id}
          <button class="link-button" onclick={() => navigate(`/artist/${encodeURIComponent(album.artist_id)}`)}>
            {album.album_artist}
          </button>
        {:else}
          <p style="color: var(--text-muted); margin: 0">{album.album_artist}</p>
        {/if}
        <p style="color: var(--text-muted); font-size: 0.82rem; margin: 4px 0 0">
          {album.year ?? ""}{album.year ? " · " : ""}{album.track_count} tracks · {formatDuration(album.total_duration_seconds)}
          {#if album.offline_track_count}
            · <span style="color: var(--danger)">{album.offline_track_count} offline</span>
          {/if}
        </p>
        <button
          class="badge"
          style="margin-top:14px; font-size:0.85rem; padding:8px 20px"
          onclick={playAll}
        >
          ▶ Play album
        </button>
      </div>

      <div class="album-tracks-pane">
        <div class="section-title">Tracks</div>
        <TrackList tracks={album.tracks} />
      </div>
    </div>
  </div>
{/if}

<style>
  .album-hero-row {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .album-art-img {
    width: min(60vw, 280px);
    height: min(60vw, 280px);
    border-radius: 16px;
    object-fit: cover;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
  }

  /* Wide (desktop-app) viewports: break out of the app's narrow centered
     column and lay the art out on the left, with the track list in its
     own panel on the right so it can scroll independently of the art. */
  @media (min-width: 900px) {
    .album-page {
      width: 100vw;
      max-width: 1100px;
      position: relative;
      left: 50%;
      transform: translateX(-50%);
      padding: 0 24px;
      box-sizing: border-box;
    }

    .album-hero-row {
      flex-direction: row;
      align-items: flex-start;
      text-align: left;
      gap: 40px;
    }

    .album-art-pane {
      flex: 0 0 300px;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      position: sticky;
      top: 24px;
    }

    .album-art-img {
      width: 300px;
      height: 300px;
    }

    .album-tracks-pane {
      flex: 1;
      min-width: 0;
      max-height: calc(100vh - 48px);
      overflow-y: auto;
    }
  }
</style>
