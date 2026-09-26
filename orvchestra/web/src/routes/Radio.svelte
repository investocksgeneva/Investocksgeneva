<script>
  import { api } from "../lib/api.js";
  import { playRadioStation } from "../lib/player.svelte.js";

  let query = $state("");
  let results = $state([]);
  let searching = $state(false);
  let searchError = $state(null);
  let stations = $state([]);
  let timer;

  async function loadStations() {
    stations = await api.radioStations();
  }
  loadStations();

  function onInput() {
    clearTimeout(timer);
    const current = query;
    timer = setTimeout(async () => {
      if (!current.trim()) {
        results = [];
        searchError = null;
        return;
      }
      searching = true;
      searchError = null;
      try {
        results = await api.radioSearch(current);
      } catch (err) {
        results = [];
        searchError = String(err.message || err);
      } finally {
        searching = false;
      }
    }, 300);
  }

  function isSaved(id) {
    return stations.some((s) => s.id === id);
  }

  async function saveStation(station) {
    await api.radioSave(station);
    await loadStations();
  }

  async function removeStation(id) {
    await api.radioRemove(id);
    await loadStations();
  }
</script>

<h1>Radio</h1>
<input class="search-input" type="search" placeholder="Search stations…" bind:value={query} oninput={onInput} />

{#if stations.length}
  <div class="section-title">My stations</div>
  <div class="row-list">
    {#each stations as station (station.id)}
      <div class="row-item">
        {#if station.favicon}
          <img class="row-art" src={station.favicon} alt="" loading="lazy" />
        {:else}
          <div class="row-art art-placeholder"></div>
        {/if}
        <button class="row-text" style="text-align:left; flex:1;" onclick={() => playRadioStation(station)}>
          <div class="row-title">{station.name}</div>
          <div class="row-subtitle">{station.tags || station.country || "Internet radio"}</div>
        </button>
        <button class="icon-button" aria-label="Remove station" onclick={() => removeStation(station.id)}>✕</button>
      </div>
    {/each}
  </div>
{/if}

{#if searching}
  <p class="empty-state">Searching…</p>
{:else if searchError}
  <p class="empty-state">Couldn't search stations: {searchError}</p>
{:else if query.trim() && !results.length}
  <p class="empty-state">No stations found for "{query}".</p>
{/if}

{#if results.length}
  <div class="section-title">Search results</div>
  <div class="row-list">
    {#each results as station (station.id)}
      <div class="row-item">
        {#if station.favicon}
          <img class="row-art" src={station.favicon} alt="" loading="lazy" />
        {:else}
          <div class="row-art art-placeholder"></div>
        {/if}
        <button class="row-text" style="text-align:left; flex:1;" onclick={() => playRadioStation(station)}>
          <div class="row-title">{station.name}</div>
          <div class="row-subtitle">{station.tags || station.country || "Internet radio"}</div>
        </button>
        <button
          class="icon-button"
          aria-label={isSaved(station.id) ? "Already saved" : "Save station"}
          onclick={() => saveStation(station)}
        >
          {isSaved(station.id) ? "★" : "☆"}
        </button>
      </div>
    {/each}
  </div>
{/if}

{#if !stations.length && !query.trim()}
  <p class="empty-state">Search for a station above to get started -- e.g. a station name, genre, or city.</p>
{/if}
