<script>
  import { onMount } from "svelte";
  import { api } from "../lib/api.js";
  import TrackList from "../lib/TrackList.svelte";

  let playlists = $state([]);
  let expandedId = $state(null);
  let expandedTracks = $state([]);
  let creating = $state(false);
  let error = $state(null);

  let name = $state("");
  let genre = $state("");
  let yearMin = $state("");
  let yearMax = $state("");
  let minRating = $state("");
  let minPlayCount = $state("");
  let sort = $state("title");

  async function refresh() {
    playlists = await api.playlists();
  }

  onMount(refresh);

  async function toggleExpand(playlist) {
    if (expandedId === playlist.id) {
      expandedId = null;
      return;
    }
    const full = await api.playlist(playlist.id);
    expandedTracks = full.tracks ?? [];
    expandedId = playlist.id;
  }

  async function removePlaylist(id) {
    await api.deletePlaylist(id);
    if (expandedId === id) expandedId = null;
    await refresh();
  }

  async function createPlaylist() {
    if (!name.trim()) return;
    creating = true;
    error = null;
    try {
      const rules = {
        genre: genre.trim() || undefined,
        year_min: yearMin === "" ? undefined : Number(yearMin),
        year_max: yearMax === "" ? undefined : Number(yearMax),
        min_rating: minRating === "" ? undefined : Number(minRating),
        min_play_count: minPlayCount === "" ? undefined : Number(minPlayCount),
        sort,
      };
      await api.createSmartPlaylist(name.trim(), null, rules);
      name = genre = yearMin = yearMax = minRating = minPlayCount = "";
      await refresh();
    } catch (err) {
      error = String(err.message || err);
    } finally {
      creating = false;
    }
  }
</script>

<h1>Playlists</h1>

<div class="section-title">New smart playlist</div>
<div style="display:flex; flex-direction:column; gap:8px; margin-bottom: 20px">
  <input class="search-input" placeholder="Name" bind:value={name} />
  <input class="search-input" placeholder="Genre (optional)" bind:value={genre} />
  <div style="display:flex; gap:8px">
    <input class="search-input" type="number" placeholder="Year from" bind:value={yearMin} />
    <input class="search-input" type="number" placeholder="Year to" bind:value={yearMax} />
  </div>
  <div style="display:flex; gap:8px">
    <select class="search-input" bind:value={minRating}>
      <option value="">Any rating</option>
      {#each [1, 2, 3, 4, 5] as r (r)}
        <option value={r}>{r}+ stars</option>
      {/each}
    </select>
    <input class="search-input" type="number" placeholder="Min plays" bind:value={minPlayCount} />
  </div>
  <select class="search-input" bind:value={sort}>
    <option value="title">Sort: title</option>
    <option value="artist">Sort: artist</option>
    <option value="recently_added">Sort: recently added</option>
    <option value="random">Sort: shuffle</option>
  </select>
  {#if error}<p class="empty-state" style="padding: 4px 0">{error}</p>{/if}
  <button class="badge" style="padding: 10px; font-size: 0.9rem" onclick={createPlaylist} disabled={creating}>
    {creating ? "Creating…" : "Create playlist"}
  </button>
</div>

<div class="section-title">Your playlists</div>
{#if playlists.length === 0}
  <p class="empty-state">No playlists yet — build one above.</p>
{:else}
  <div class="row-list">
    {#each playlists as playlist (playlist.id)}
      <div class="row-item">
        <button class="open-now-playing" onclick={() => toggleExpand(playlist)}>
          <div class="row-text">
            <div class="row-title">{playlist.name}</div>
            {#if playlist.rules}
              <div class="row-subtitle">
                {[
                  playlist.rules.genre,
                  playlist.rules.min_rating ? `${playlist.rules.min_rating}+ stars` : null,
                  playlist.rules.year_min || playlist.rules.year_max
                    ? `${playlist.rules.year_min ?? ""}–${playlist.rules.year_max ?? ""}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "All tracks"}
              </div>
            {/if}
          </div>
        </button>
        <button class="icon-button" style="font-size: 1rem" aria-label="Delete playlist" onclick={() => removePlaylist(playlist.id)}>
          ✕
        </button>
      </div>
      {#if expandedId === playlist.id}
        <TrackList tracks={expandedTracks} showArt showAlbum />
      {/if}
    {/each}
  </div>
{/if}
