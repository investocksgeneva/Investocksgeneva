<script>
  import { onMount } from "svelte";
  import { api } from "../lib/api.js";
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
  <p class="empty-state">Listening history arrives in Phase 4.</p>

  <div class="section-title">Rediscover</div>
  <p class="empty-state">Albums you haven't played in a while will show up here once Phase 4 tracks plays.</p>
{/if}
