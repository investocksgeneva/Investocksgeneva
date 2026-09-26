<script>
  import { api } from "../lib/api.js";
  import AlbumGrid from "../lib/AlbumGrid.svelte";

  let { year } = $props();

  let data = $state(null);

  $effect(() => {
    data = null;
    api.year(year).then((y) => (data = y));
  });
</script>

{#if !data}
  <p class="empty-state">Loading…</p>
{:else}
  <h1>{data.year}</h1>
  <AlbumGrid albums={data.albums} />
{/if}
