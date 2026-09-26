<script>
  import { api } from "../lib/api.js";
  import { navigate } from "../lib/router.svelte.js";
  import AlbumGrid from "../lib/AlbumGrid.svelte";
  import TrackList from "../lib/TrackList.svelte";

  let query = $state("");
  let results = $state({ artists: [], albums: [], tracks: [] });
  let searching = $state(false);
  let timer;

  function onInput() {
    clearTimeout(timer);
    const current = query;
    timer = setTimeout(async () => {
      searching = true;
      try {
        results = await api.search(current);
      } finally {
        searching = false;
      }
    }, 200);
  }

  const hasAnyResults = $derived(results.artists.length || results.albums.length || results.tracks.length);
</script>

<h1>Search</h1>
<input
  class="search-input"
  type="search"
  placeholder="Artists, albums, tracks…"
  bind:value={query}
  oninput={onInput}
/>

{#if query.trim() && !searching && !hasAnyResults}
  <p class="empty-state">No matches for "{query}".</p>
{/if}

{#if results.artists.length}
  <div class="section-title">Artists</div>
  <div class="row-list">
    {#each results.artists as artist (artist.id)}
      <button class="row-item" onclick={() => navigate(`/artist/${encodeURIComponent(artist.id)}`)}>
        <div class="row-text">
          <div class="row-title">{artist.artist}</div>
          <div class="row-subtitle">{artist.album_count} albums</div>
        </div>
      </button>
    {/each}
  </div>
{/if}

{#if results.albums.length}
  <div class="section-title">Albums</div>
  <AlbumGrid albums={results.albums} />
{/if}

{#if results.tracks.length}
  <div class="section-title">Tracks</div>
  <TrackList tracks={results.tracks} showArt showAlbum />
{/if}
