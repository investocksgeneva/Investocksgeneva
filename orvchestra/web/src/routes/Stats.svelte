<script>
  import { api, formatDuration } from "../lib/api.js";
  import AlbumGrid from "../lib/AlbumGrid.svelte";
  import { navigate } from "../lib/router.svelte.js";

  const PERIODS = [
    { value: "7", label: "7 days" },
    { value: "30", label: "30 days" },
    { value: "90", label: "90 days" },
    { value: "365", label: "Year" },
    { value: "all", label: "All time" },
  ];
  const KINDS = [
    { value: "tracks", label: "Tracks" },
    { value: "artists", label: "Artists" },
    { value: "albums", label: "Albums" },
  ];

  let period = $state("30");
  let kind = $state("tracks");
  let summary = $state(null);
  let topItems = $state([]);
  let encore = $state([]);
  let wrappedYear = $state(new Date().getFullYear());
  let wrapped = $state(null);
  let loadingWrapped = $state(false);

  async function loadSummaryAndTop() {
    summary = await api.statsSummary(period);
    topItems = await api.statsTop(kind, period, 10);
  }

  $effect(() => {
    // Re-run whenever period or kind changes.
    period;
    kind;
    loadSummaryAndTop();
  });

  $effect(() => {
    api.statsEncore(12).then((rows) => (encore = rows));
  });

  function formatHours(totalSeconds) {
    const hours = totalSeconds / 3600;
    return hours < 10 ? `${hours.toFixed(1)}h` : `${Math.round(hours)}h`;
  }

  async function loadWrapped() {
    loadingWrapped = true;
    try {
      wrapped = await api.statsWrapped(wrappedYear);
    } finally {
      loadingWrapped = false;
    }
  }
</script>

<h1>Stats</h1>

<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom: 4px">
  {#each PERIODS as p (p.value)}
    <button
      class="badge"
      style="background: {period === p.value ? 'var(--accent)' : 'var(--bg-card)'}; color: {period === p.value ? 'var(--accent-text)' : 'var(--text-muted)'}"
      onclick={() => (period = p.value)}
    >
      {p.label}
    </button>
  {/each}
</div>

{#if summary}
  <div class="grid" style="grid-template-columns: repeat(2, 1fr); margin-top: 16px">
    <div class="card"><div class="card-body">
      <div class="subtitle">Listening time</div>
      <div class="title" style="font-size: 1.3rem">{formatHours(summary.total_seconds)}</div>
    </div></div>
    <div class="card"><div class="card-body">
      <div class="subtitle">Plays</div>
      <div class="title" style="font-size: 1.3rem">{summary.play_count}</div>
    </div></div>
  </div>

  {#if summary.format_mix.length}
    <div class="section-title">Format mix</div>
    <div class="row-list">
      {#each summary.format_mix as row (row.codec)}
        <div class="row-item">
          <div class="row-text row-title">{row.codec}</div>
          <span class="badge">{row.play_count}</span>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<div class="section-title" style="display:flex; justify-content:space-between; align-items:center">
  <span>Top</span>
  <span>
    {#each KINDS as k (k.value)}
      <button
        style="font-size:0.8rem; margin-left:10px; color: {kind === k.value ? 'var(--accent)' : 'var(--text-muted)'}"
        onclick={() => (kind = k.value)}
      >
        {k.label}
      </button>
    {/each}
  </span>
</div>

{#if topItems.length === 0}
  <p class="empty-state">Nothing played in this period yet.</p>
{:else if kind === "albums"}
  <AlbumGrid albums={topItems} />
{:else}
  <div class="row-list">
    {#each topItems as item, index (item.id ?? item.artist)}
      <button
        class="row-item"
        onclick={() => kind === "tracks" && navigate(`/album/${encodeURIComponent(item.album_id)}`)}
      >
        <span class="row-index">{index + 1}</span>
        <div class="row-text">
          <div class="row-title">{item.title ?? item.artist}</div>
          {#if item.artist && item.title}<div class="row-subtitle">{item.artist}</div>{/if}
        </div>
        <span class="badge">{item.play_count}</span>
      </button>
    {/each}
  </div>
{/if}

{#if encore.length}
  <div class="section-title">Encore — haven't played in a while</div>
  <AlbumGrid albums={encore} />
{/if}

<div class="section-title">Wrapped</div>
<div style="display:flex; gap:10px; align-items:center; margin-bottom: 12px">
  <input
    class="search-input"
    style="width:100px"
    type="number"
    bind:value={wrappedYear}
  />
  <button class="badge" onclick={loadWrapped}>{loadingWrapped ? "Loading…" : "Show"}</button>
</div>

{#if wrapped}
  <p style="color: var(--text-muted); margin-top: -6px">
    {wrapped.play_count} plays · {formatHours(wrapped.total_seconds)} of listening in {wrapped.year}
  </p>
  {#if wrapped.top_artists.length}
    <div class="section-title">Top artists that year</div>
    <div class="row-list">
      {#each wrapped.top_artists as artist, index (artist.artist)}
        <div class="row-item">
          <span class="row-index">{index + 1}</span>
          <div class="row-text row-title">{artist.artist}</div>
          <span class="badge">{artist.play_count}</span>
        </div>
      {/each}
    </div>
  {/if}
  {#if wrapped.top_albums.length}
    <div class="section-title">Top albums that year</div>
    <AlbumGrid albums={wrapped.top_albums} />
  {/if}
{/if}
