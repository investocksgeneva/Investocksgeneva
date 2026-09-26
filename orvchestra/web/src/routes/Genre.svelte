<script>
  import { api } from "../lib/api.js";
  import TrackList from "../lib/TrackList.svelte";

  let { id } = $props();

  let genre = $state(null);

  $effect(() => {
    genre = null;
    api.genre(id).then((g) => (genre = g));
  });
</script>

{#if !genre}
  <p class="empty-state">Loading…</p>
{:else}
  <h1>{genre.name}</h1>
  <TrackList tracks={genre.tracks} showArt showAlbum />
{/if}
