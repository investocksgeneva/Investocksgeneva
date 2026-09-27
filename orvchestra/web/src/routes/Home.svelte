<script>
  import { onMount } from "svelte";
  import { api, formatCompactNumber } from "../lib/api.js";
  import AlbumGrid from "../lib/AlbumGrid.svelte";

  let data = $state(null);
  let error = $state(null);

  onMount(async () => {
    try {
      data = await api.home();
    } catch (err) {
      error = String(err.message || err);
    }
  });
</script>

<h1>Home</h1>

{#if error}
  <p class="empty-state">Couldn't load your library: {error}</p>
{:else if !data}
  <p class="empty-state">Loading…</p>
{:else}
  <div class="section-title">Recently added</div>
  {#if data.recently_added.length}
    <AlbumGrid albums={data.recently_added} />
  {:else}
    <p class="empty-state">Nothing scanned yet — run <code>orvchestra scan</code>.</p>
  {/if}

  <div class="section-title">Recently played</div>
  {#if data.recently_played.length}
    <AlbumGrid albums={data.recently_played} />
  {:else}
    <p class="empty-state">Nothing played yet — play something and it'll show up here.</p>
  {/if}

  <div class="section-title">Rediscover</div>
  {#if data.rediscover.length}
    <AlbumGrid albums={data.rediscover} />
  {:else}
    <p class="empty-state">Albums you haven't played in 12+ months will show up here.</p>
  {/if}

  <div class="section-title">Library</div>
  <div class="stat-tiles">
    <div class="stat-tile">
      <div class="stat-value">{formatCompactNumber(data.library.tracks)}</div>
      <div class="stat-label">Songs</div>
    </div>
    <div class="stat-tile">
      <div class="stat-value">{formatCompactNumber(data.library.albums)}</div>
      <div class="stat-label">Albums</div>
    </div>
    <div class="stat-tile">
      <div class="stat-value">{formatCompactNumber(data.library.artists)}</div>
      <div class="stat-label">Artists</div>
    </div>
  </div>
{/if}
