<script>
  import { navigate } from "./router.svelte.js";

  let { albums } = $props();
</script>

<div class="grid">
  {#each albums as album (album.id)}
    <button class="card" onclick={() => navigate(`/album/${encodeURIComponent(album.id)}`)}>
      {#if album.art_url_small}
        <img src={album.art_url_small} alt="" loading="lazy" />
      {:else}
        <div class="art-placeholder"></div>
      {/if}
      <div class="card-body">
        <div class="title">{album.album}</div>
        <div class="subtitle">{album.album_artist}{album.year ? ` · ${album.year}` : ""}</div>
      </div>
    </button>
  {/each}
</div>
